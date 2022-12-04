import os
import sys
from osgeo import ogr


gml_txt = '''<gml:Polygon>
  <gml:outerBoundaryIs>
    <gml:LinearRing>
      <gml:coordinates>
        366759.222,6677450.3509 366729.1256,6677417.0045 366728.5965,6677408.8024 366726.2152,6677402.1878 366714.8381,6677390.2815 366707.1652,6677380.2273 366687.8505,6677391.0752 366684.9401,6677391.6044 366660.0692,6677371.7606 366620.1171,6677429.1753 
        366541.4695,6677411.7789 366604.0436,6677325.7892 366574.4102,6677299.0662 366640.6885,6677238.8734 366742.5533,6677339.1507 366830.3951,6677430.1675 366820.3409,6677453.3936 366759.222,6677450.3509 
      </gml:coordinates>
    </gml:LinearRing>
  </gml:outerBoundaryIs>
</gml:Polygon>'''
g = ogr.CreateGeometryFromGML(gml_txt)
outshp = 'out.shp'
out_shp = ogr.GetDriverByName('ESRI Shapefile').CreateDataSource(outshp)
out_lyr = out_shp.CreateLayer( os.path.basename(outshp) )
f = ogr.Feature(out_lyr.GetLayerDefn())
f.SetGeometry(g)
out_lyr.CreateFeature(f)
