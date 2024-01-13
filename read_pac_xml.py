import csv
import os
import json
import sys
import ssl
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from itertools import groupby, chain
from osgeo import gdal, ogr, osr
import argparse

try:
    from lxml import etree, objectify
except ImportError:
    print("Failed to import etree or objectify from lxml")
    sys.exit(0)

parser = argparse.ArgumentParser()
parser.add_argument("path", type=str,
                    help="Provide path to xml file")
args = parser.parse_args()

local_path = args.path

with open(local_path, encoding="ISO-8859-1") as req:
    xml_content = etree.parse(req)

metadata = local_path
parser = etree.XMLParser(remove_blank_text=True)
xml_content = etree.parse(metadata, parser)
root = xml_content.getroot()

for elem in root.getiterator():
    if not hasattr(elem.tag, 'find'): continue  # guard for Comment tags
    i = elem.tag.find('}')
    if i >= 0:
        elem.tag = elem.tag[i+1:]
objectify.deannotate(root, cleanup_namespaces=True)

# source = osr.SpatialReference()
# source.ImportFromEPSG(2154)

# target = osr.SpatialReference()
# target.ImportFromEPSG(4326)

# transform = osr.CoordinateTransformation(source, target)

def createFeatureCollection(features,crs=None):
    geojson_content = {
        "type": "FeatureCollection",
        "features": features
    }
    if crs is not None:
        geojson_content["crs"] = { "type": "name", "properties": { "name": f"urn:ogc:def:crs:EPSG::{str(crs)}" }}
    return geojson_content

def cleanDictKeys(dictionnary):
    return {key.replace('-','_'): val for key,val in dictionnary.items()}

attribs_associes_ou_identite_individu = ['civilite', 'nom', 'prenoms']
sna_internal_counter = 0

ilot_features = []
zdh_declarees_features = []
sna_declarees_features_points = []
sna_declarees_features_polygons = []
parcelles_features = []

pieces_jointes = []
producteur_infos = []
infos_individu = []
infos_societe = []
infos_associes = []
infos_maec_prm = []
infos_demandes_aides_pilier1 = []
infos_demandes_aides_pilier2 = []
infos_effectifs_animaux = []
infos_effectifs_transhumants = []

intersection_sna_ilots = []
intersection_sna_parcelles = []

for child in xml_content.getroot().getchildren():
    producteur_infos.append(cleanDictKeys(child.attrib))
    demandeur = child.find('demandeur')
    identification_societe = demandeur.find('identification-societe')
    identification_individu = demandeur.find('identification-individuelle')
    siret = demandeur.find('siret').text
    iban = cleanDictKeys(demandeur.find('iban').attrib)
    courriel = demandeur.find('courriel').text
    if identification_societe is not None:
        exploitation = identification_societe.find('exploitation')
        exploitation = exploitation.text if exploitation is not None else None
        infos_associes = infos_associes + [cleanDictKeys({
            **associe.attrib,
            **{attrib_associes: associe.find('identite').find(attrib_associes).text for attrib_associes in attribs_associes_ou_identite_individu},
            "numero_fiscal": associe.find('numero-fiscal').text,
            "siret": siret
        }) for associe in identification_societe.findall('.//associe')]
        infos_societe_content = {
            "exploitation": exploitation,
            **dict(demandeur.attrib),
            "courriel": courriel,
            "siret": siret,
            **iban
        }
        infos_societe.append(cleanDictKeys(infos_societe_content))
    if identification_individu is not None:
        # import ipdb;ipdb.set_trace()
        infos_individu_content = {
            **{attrib_associes: identification_individu.find('identite').find(attrib_associes).text for attrib_associes in attribs_associes_ou_identite_individu},
            **dict(demandeur.attrib),
            "courriel": courriel,
            "siret": siret,
            **iban
        }
        infos_individu.append(cleanDictKeys(infos_individu_content))

    effectifs_animaux = child.findall('.//effectif-animal')
    for effectif_animal in effectifs_animaux:
        effectifs_present_ou_transhumant = effectif_animal.findall('effectif-present-ou-transhumant')
        for present_ou_transhumant in effectifs_present_ou_transhumant:
            type_animal_1 = present_ou_transhumant.find('type-animal-1').text
            nb_animaux_1 = present_ou_transhumant.find('nb-animaux-1').text
            infos_effectifs_animaux.append({
                "type_animal_1": type_animal_1,
                "nb_animaux_1": nb_animaux_1
            })
            for effectif_transhumant in present_ou_transhumant.findall('.//effectif-transhumant'):
                infos_effectifs_transhumants.append({
                    "type_animal_1": type_animal_1,
                    "nb-animaux-recus": effectif_transhumant.find('nb-animaux-recus').text,
                    "estive": effectif_transhumant.find('estive').text,
                    "nom-exploitant": effectif_transhumant.find('nom-exploitant').text,
                    "departement": effectif_transhumant.find('departement').text,
                    "commune": effectif_transhumant.find('commune').text
                })

    maec_prm = child.find('maec-prm')
    femelle_reproductrice = maec_prm.find('femelle-reproductrice')
    infos_maec_prm.append(cleanDictKeys({
        **femelle_reproductrice.attrib,
        **femelle_reproductrice.find('nombre-animaux').attrib,
        **maec_prm.find('organisme-gestionnaire-race').attrib
    }))

    demandes_aides_pilier1_et_AR = child.find('demandes-aides-pilier1-et-AR')
    values_pilier1 = [i.attrib for i in demandes_aides_pilier1_et_AR.getchildren()]
    infos_demandes_aides_pilier1.append(cleanDictKeys({
        **demandes_aides_pilier1_et_AR.attrib,
        **{k: v for d in values_pilier1 for k, v in d.items()}
    }))
    
    demandes_aides_pilier2 = child.find('demandes-aides-pilier2')

    values_pilier2 = [i.attrib for i in demandes_aides_pilier2.getchildren()]
    infos_demandes_aides_pilier2.append(cleanDictKeys({
        **demandes_aides_pilier2.attrib,
        **{k: v for d in values_pilier2 for k, v in d.items()}
    }))

    # print([i.tag for i in child.getchildren()])
    for pj in child.find('pieces-jointes').findall('./pj'):
        pieces_jointes.append(cleanDictKeys({
            **pj.attrib,
            "intitule": pj.find('intitule').text
        }))
    rpg = child.find('rpg')
    zdh_declarees = rpg.findall('zdh-declaree')
    for zdh in zdh_declarees:
        geom_zdh = zdh.find('geometrie')
        gml_content_zdh = etree.tostring(geom_zdh.getchildren()[0])
        gml_content_zdh = gml_content_zdh.decode('utf-8')
        g_zdh = ogr.CreateGeometryFromGML(gml_content_zdh)
        # g_zdh.Transform(transform)
        feature_zdh_geometry = g_zdh.ExportToJson()
        g_zdh = None
        zdh_declarees_features.append({
          "type": "Feature",
          "properties": {
              "numero_zdh": zdh.find("numeroZdh").text if zdh.find("numeroZdh") is not None else "",
              "densite_vegetation": zdh.find("densiteVegetation").text,
              "numero_zdh_creation_tas": zdh.find("numeroZdhcreationTas").text if zdh.find("numeroZdhcreationTas") is not None else "",
          },
          "geometry": json.loads(feature_zdh_geometry)
        })
    sna_declarees = rpg.findall('sna-declaree')
    for sna in sna_declarees:
        geom_sna = sna.find('geometrie')
        gml_content_sna = etree.tostring(geom_sna.getchildren()[0])
        gml_content_sna = gml_content_sna.decode('utf-8')
        g_sna = ogr.CreateGeometryFromGML(gml_content_sna)
        # g_sna.Transform(transform)
        feature_sna_geometry = g_sna.ExportToJson()
        g_sna = None
        feature_sna_geometry = json.loads(feature_sna_geometry)

        if sna.find("numeroSna") is None:
            numero_sna = sna_internal_counter
            sna_internal_counter += 1
        else:
            numero_sna = sna.find("numeroSna").text

        numero_sna_padded_12 = str(numero_sna).zfill(12)

        numero_sna_creation_tas = sna.find('numeroSnacreationTas').text if sna.find('numeroSnacreationTas') is not None else None
        if "Point" in feature_sna_geometry.get("type"):
            sna_declarees_features_points.append({
              "type": "Feature",
              "properties": {
                  "numero_sna": numero_sna_padded_12,
                  "numero_sna_creation_tas": numero_sna_creation_tas,
                  "categorie_sna": sna.find("categorieSna").text,
                  "type_sna": sna.find("typeSna").text,
                  "mur_traditionnel_pierre_sie": sna.find("murTraditionnelPierreSIE").text if sna.find("murTraditionnelPierreSIE") is not None else "",
              },
              "geometry": feature_sna_geometry
            })
        else:
            sna_declarees_features_polygons.append({
              "type": "Feature",
              "properties": {
                  "numero_sna": numero_sna_padded_12,
                  "numero_sna_creation_tas": numero_sna_creation_tas,
                  "categorie_sna": sna.find("categorieSna").text,
                  "type_sna": sna.find("typeSna").text,
                  "mur_traditionnel_pierre_sie": sna.find("murTraditionnelPierreSIE").text if sna.find("murTraditionnelPierreSIE") is not None else "",
              },
              "geometry": feature_sna_geometry
            })
        for intersectionSnaIlot in sna.findall('.//intersectionSnaIlot'):
            intersection_sna_ilots.append({
                "numero_ilot": intersectionSnaIlot.find("numeroIlot").text,
                "largeur": intersectionSnaIlot.find("largeur").text if intersectionSnaIlot.find("largeur") is not None else None,
                "numero_sna": numero_sna_padded_12,
                "type_sna": sna.find("typeSna").text
            })

        for intersectionSnaParcelle in sna.findall('.//intersectionSnaParcelle'):
            intersection_sna_parcelles.append({
                "numero_ilot": intersectionSnaParcelle.find("numeroIlot").text,
                "numero_sna": numero_sna_padded_12,
                "numero_parcelle": intersectionSnaParcelle.find("numeroParcelle").text,
                "longueur_sie": intersectionSnaParcelle.find("longueur-sie").text if intersectionSnaParcelle.find("longueur-sie") is not None else None,
                "nombre_arbres": intersectionSnaParcelle.find("nombreArbres").text if intersectionSnaParcelle.find("nombreArbres") is not None else None
            })

    ilots = rpg.findall('ilot')
    for ilot in ilots:
        parcelles = ilot.findall('.//parcelle')
        properties_ilot = cleanDictKeys({
            "commune" : ilot.find('commune').text,
            **ilot.attrib
        })
        geom = ilot.find('geometrie')
        gml_content = etree.tostring(geom.getchildren()[0])
        gml_content = gml_content.decode('utf-8')
        g_ilot = ogr.CreateGeometryFromGML(gml_content)
        # g_ilot.Transform(transform)
        feature_geometry = g_ilot.ExportToJson()
        g_ilot = None
        ilot_features.append({
          "type": "Feature",
          "properties": properties_ilot,
          "geometry": json.loads(feature_geometry)
        })

        for parcelle in parcelles:
            descriptif_parcelle = parcelle.find('descriptif-parcelle')
            surface_admissible = parcelle.find('surface-admissible')
            culture_principale = descriptif_parcelle.find('culture-principale')
            engagements_maec = descriptif_parcelle.find('engagements-maec')
            
            properties_parcelle = cleanDictKeys({
                "code_culture": culture_principale.find('code-culture').text,
                "precision": culture_principale.find('code-culture').text if culture_principale.find('code-culture') is not None else None,
                "reconversion_pp": culture_principale.find('reconversion-pp').text if culture_principale.find('reconversion-pp') is not None else None,
                "retournement_pp": culture_principale.find('retournement-pp').text if culture_principale.find('retournement-pp') is not None else None,
                "surface_admissible": surface_admissible.text if surface_admissible is not None else None,
                **descriptif_parcelle.attrib,
                **culture_principale.attrib,
                **properties_ilot
            })
            if engagements_maec is not None:
                properties_parcelle = {
                    **properties_parcelle,
                    **cleanDictKeys(engagements_maec.attrib)
                }
            geom_parcelle = parcelle.find('geometrie')
            gml_content_parcelle = etree.tostring(geom_parcelle.getchildren()[0])
            gml_content_parcelle = gml_content_parcelle.decode('utf-8')
            g_parcelle = ogr.CreateGeometryFromGML(gml_content_parcelle)
            # g_parcelle.Transform(transform)
            feature_parcelle_geometry = g_parcelle.ExportToJson()
            g_parcelle = None
            parcelles_features.append({
              "type": "Feature",
              "properties": properties_parcelle,
              "geometry": json.loads(feature_parcelle_geometry)
            })

list_geojson = {
    'ilots': ilot_features,
    'parcelles_ilots': parcelles_features,
    'zdh_declarees': zdh_declarees_features,
    'sna_declarees_points': sna_declarees_features_points,
    'sna_declarees_polygons': sna_declarees_features_polygons
}

for k, v in list_geojson.items():
    with open(f'{k}.geojson', 'w') as outfile:
        json.dump(createFeatureCollection(v, 2154), outfile)

list_csv = {
    'pieces_jointes': pieces_jointes,
    'producteur_infos': producteur_infos,
    'infos_maec_prm': infos_maec_prm,
    'infos_demandes_aides_pilier1': infos_demandes_aides_pilier1,
    'infos_demandes_aides_pilier2': infos_demandes_aides_pilier2,
    'intersection_sna_ilots': intersection_sna_ilots,
    'intersection_sna_parcelles': intersection_sna_parcelles,
    'infos_effectifs_animaux': infos_effectifs_animaux,
    'infos_effectifs_transhumants': infos_effectifs_transhumants
}

if len(infos_societe) > 0:
    list_csv['infos_societe'] = infos_societe
    list_csv['infos_associes'] = infos_associes

if len(infos_individu) > 0:
    list_csv['infos_individu'] = infos_individu

for k, v in list_csv.items():
    with open(f'{k}.csv', 'w', encoding='utf8', newline='') as outfile:
        fc = csv.DictWriter(outfile, fieldnames=v[0].keys())
        fc.writeheader()
        fc.writerows(v)

counter = 0
for k, v in list_geojson.items():
    gdal_options = f'-f GPKG {k} -overwrite -nln {k}'
    if counter > 0:
        gdal_options += ' -update'

    gdal.VectorTranslate(
        local_path.replace('.xml', '.gpkg'),
        f'{k}.geojson',
        options=gdal_options
    )
    counter += 1

for k, v in list_csv.items():
    gdal_options = f'-f GPKG {k} -overwrite -nln {k} -update'
    gdal.VectorTranslate(
        local_path.replace('.xml', '.gpkg'),
        f'{k}.csv',
        options=gdal_options
    )
