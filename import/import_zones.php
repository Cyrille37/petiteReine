<?php
require __DIR__ . '/../conf.php';
set_time_limit(300);

try {
  $PDO = new PDO('pgsql:host=' . DB_HOST . ';dbname=' . DB_NAME, DB_USER, DB_PASSWORD);
} catch (Exception $e) {
  die("Unable to connect database");
}

$areaCriterion = '' . (3600000000 + OSM_ZONE) . '';
$postdata = http_build_query(array('data' => '
[timeout:20][out:json];
area(' . $areaCriterion . ')->.zone;
(   
 relation(area.zone)[admin_level=8][boundary=administrative]->.bounds;
  (
    way(r.bounds);>;
  );
);
out ;
'));
$opts = array(
  'http' =>
  array(
    'method' => 'POST',
    'header' => 'Content-type: application/x-www-form-urlencoded',
    'content' => $postdata
  )
);

$context = stream_context_create($opts);
$result = file_get_contents(OAPI_URL, false, $context);

if (! $result)
  throw new InvalidArgumentException('Overpass query no result');

// Charger le fichier OSM/Overpass JSON
$osmData = json_decode($result, true);

// Vérifier la présence de la clé "elements"
if (!isset($osmData['elements'])) {
  die("Erreur : La clé 'elements' est introuvable dans le fichier. Vérifiez que le fichier est bien un export OSM/Overpass JSON.");
}


// Fonction pour ordonner les 'way' d'une relation
function orderWaysForRelation(array $relation, array $ways): array {
    $wayIds = [];
    foreach ($relation['members'] as $member) {
        if ($member['type'] === 'way') {
            $wayIds[] = $member['ref'];
        }
    }

    if (empty($wayIds)) {
        return [];
    }

    // Initialisation : on part du premier 'way' de la liste
    $orderedWays = [];
    $remainingWayIds = $wayIds;
    $currentWayId = array_shift($remainingWayIds);
    $orderedWays[] = $ways[$currentWayId];

    // Tant qu'il reste des 'way' à ordonner
    while (!empty($remainingWayIds)) {
        $lastWay = end($orderedWays);
        $lastNode = end($lastWay['nodes']);

        $foundNext = false;
        foreach ($remainingWayIds as $key => $wayId) {
            $way = $ways[$wayId];
            $firstNode = $way['nodes'][0];

            // Si le premier nœud du 'way' actuel correspond au dernier nœud du 'way' précédent
            if ($firstNode === $lastNode) {
                $orderedWays[] = $way;
                unset($remainingWayIds[$key]);
                $foundNext = true;
                break;
            }
        }

        // Si aucun 'way' n'a été trouvé, essayer dans l'autre sens (dernier nœud du 'way' actuel = premier nœud du 'way' précédent)
        if (!$foundNext) {
            foreach ($remainingWayIds as $key => $wayId) {
                $way = $ways[$wayId];
                $lastNodeOfWay = end($way['nodes']);

                if ($lastNodeOfWay === $lastNode) {
                    // Inverser l'ordre des nœuds du 'way' pour qu'il s'enchaîne correctement
                    $way['nodes'] = array_reverse($way['nodes']);
                    $orderedWays[] = $way;
                    unset($remainingWayIds[$key]);
                    $foundNext = true;
                    break;
                }
            }
        }

        // Si aucun 'way' n'est trouvé, le polygone est peut-être fermé
        if (!$foundNext) {
            break;
        }
    }

    return $orderedWays;
}


// Fonction pour construire un polygone WKT à partir des 'way' ordonnés
function buildPolygonWKT(array $orderedWays, array $nodes): string {
    $coordinates = [];
    foreach ($orderedWays as $way) {
        foreach ($way['nodes'] as $nodeId) {
            $node = $nodes[$nodeId] ?? null;
            if ($node) {
                $coordinates[] = "{$node['lon']} {$node['lat']}";
            } else {
                // Gérer le cas où un 'node' est manquant
                throw new Exception("Node manquant : $nodeId");
            }
        }
    }

    // Fermer le polygone
    if (!empty($coordinates)) {
        $firstCoordinate = $coordinates[0];
        $coordinates[] = $firstCoordinate;
    }

    if (count($coordinates) < 4) {
        throw new Exception("Pas assez de points pour former un polygone valide.");
    }

    return "POLYGON((" . implode(',', $coordinates) . "))";
}


$PDO = null;
try {
  $PDO = new PDO('pgsql:host=' . DB_HOST . ';dbname=' . DB_NAME, DB_USER, DB_PASSWORD);
  $PDO->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (Exception $e) {
  die("Unable to connect database");
}

$PDO->beginTransaction();

$PDO->exec('DELETE from pv_zones');
// default zone with active=1 and visible_default=1
//$PDO->exec("insert into pv_zones values ('default','Default',0,1,1,st_multi(st_expand(ST_GeomFromText('POINT(0 0)',4326),90)))");

// Extraire les éléments
$nodes = $data['elements']['node'] ?? [];
$ways = $data['elements']['way'] ?? [];
$relations = $data['elements']['relation'] ?? [];
$ways = [];
$nodes = [];
$relations = [];
foreach ($osmData['elements'] as $element) {
  if ($element['type'] === 'way') {
    $ways[$element['id']] = $element;
  } elseif ($element['type'] === 'node') {
    $nodes[$element['id']] = $element;
  } elseif ($element['type'] === 'relation') {
    $relations[$element['id']] = $element;
  }
}


// Insérer les polygones dans PostGIS
foreach ($relations as $relation) {

  if (! isset($relation['tags']['type']) || $relation['tags']['type'] != 'boundary' || $relation['tags']['admin_level'] != '8') 
{
  var_export($relation);
  echo "SKIP RELATION\n";
      continue ;
}
    $orderedWays = orderWaysForRelation($relation, $ways);
    $polygonWkt = buildPolygonWKT($orderedWays, $nodes);

    $communeName = $relation['tags']['name'];
    // Plusieurs communes avec le même code postal !
    //$zone_id = $element['tags']['postal_code'] ?? '00000';
    $zone_id = $relation['tags']['ref:INSEE'];
    $osmId = $relation['id'];

    try {
      // pv_zones (zone_id, label, osm_id, active, visible_default, geom) FROM stdin;

      $stmt = $PDO->prepare("INSERT INTO pv_zones (zone_id, label, osm_id, active, visible_default, geom) VALUES (:zone_id,:label,:osm_id,:active, :visible_default, ST_Multi(ST_GeomFromText(:geom, 4326)))");

      $stmt->execute([
        'zone_id' => $zone_id,
        ':label' => $communeName,
        ':osm_id' => $osmId,
        ':active' => 1,
        // Avec zonage toutes visibles pour affichage par défaut
        ':visible_default' => 1,
        ':geom' => $polygonWkt
      ]);
    } catch (\PDOException $e) {
      $PDO->rollBack();
      die("Erreur lors de l'insertion pour la commune $communeName : " . $e->getMessage() . "\n");
    }
  
}


try {

  $PDO->commit();
} catch (\PDOException $e) {
  die("Erreur lors du commit : " . $e->getMessage() . "\n");
}
