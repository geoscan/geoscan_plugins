"""Export by shapes plugin for Agisoft Metashape

Copyright (C) 2021  Geoscan Ltd. https://www.geoscan.aero/

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import os
import traceback
from pathlib import Path
from collections import Iterable
from typing import Callable

import numpy as np
from osgeo import gdal
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import cascaded_union

import Metashape

from common.shape_worker.shape_worker import create_shape, flatten_list
from common.shape_worker.shape_reprojection import ShapeGeometry, ShapelyGeometry
from .mtw.main import MtwCrsBuilder, raster_to_mtw


class Exporter:

    ADDITIONAL_IMAGE_FORMATS = ["MTW"]

    def __init__(self, chunk, source: str, grid_model, shapes: Iterable, path: str, format: str,
                 crs: Metashape.CoordinateSystem, mtw_crs: (tuple, None), height_correction: float,
                 resolution=None, buffer=None,
                 tiff_compression=Metashape.ImageCompression.TiffCompression.TiffCompressionLZW,
                 jpeg_quality=90, write_world=True,
                 tile_scheme=False, big_tiff=False, alpha_ch=True, tiff_overviews=True, tiled_tiff=False,
                 background_color=True, estimated_resolution: (None, tuple) = None, no_crs: bool = False,
                 nodata_value=-32767):
        """Constructor.
        :param chunk: Metashape.Chunk.
        :param source: Data type (ortho / dem).
        :param grid_model: Metashape.Elevation or Metashape.Orthomosaic. Object which must be exported.
        :param shapes: Iterable object object consisting of Metashape.Shape. Shapes for processing.
        :param path: str, or pathlike.Path. Export directory.
        :param format: str, raster format.
        :param crs: str, crs to export.
        :param mtw_crs: (tuple, None), set mtw_crs as crs for MTW if it is selected.
        :param height_correction: float, correction for DEM values.
        :param resolution: numeric. Value in meters.
        :param buffer: numeric. Set buffer value for passed shapes. Default is grid_model.resolution/2
        :param tiff_compression: ImageCompression.TiffCompression. Tiff compression. Default is LZW
        :param jpeg_quality: int. JPEG quality. Default is 90.
        :param write_world: bool. Enable/disable world file generation.
        :param tile_scheme: bool.
        :param big_tiff: bool.
        :param alpha_ch: bool.
        :param tiff_overviews: bool.
        :param tiled_tiff: bool.
        :param background_color: bool. True = white color, False = black color.
        :param estimated_resolution. (None, tuple). Estimate resolution (x, y) by gdal.Warp.
        :param no_crs: bool. Clear CRS definiton.
        :param nodata_value. (int, float). Dem export only.
        """

        self.chunk = chunk
        self.source = "ortho" if source == "Orthomosaic" else "dem"
        self.grid_model = grid_model
        self.shapes = list(shapes)

        self.path = Path(path)

        self.format = self.init_raster_format(format)
        self.crs = crs
        self.mtw_crs = mtw_crs
        self.height_correction = height_correction

        self.__tmp_shapes_group = None
        self.__labels_set = set()

        self.resolution = resolution
        self.buffer = buffer
        self.__set_boundaries()

        self.tiff_compression = tiff_compression
        self.jpeg_quality = jpeg_quality
        self.write_world = write_world
        self.tile_scheme = tile_scheme
        self.big_tiff = big_tiff
        self.alpha_ch = alpha_ch
        self.tiff_overviews = tiff_overviews
        self.tiled_tiff = tiled_tiff
        self.background_color = background_color

        self.estimated_resolution = estimated_resolution
        self.no_crs = no_crs

        self.nodata_value = nodata_value

    @property
    def tiff_compression_attr(self):
        if self.tiff_compression == 'None':
            return Metashape.ImageCompression.TiffCompression.TiffCompressionNone
        elif self.tiff_compression == 'LZW':
            return Metashape.ImageCompression.TiffCompression.TiffCompressionLZW
        elif self.tiff_compression == 'JPEG':
            return Metashape.ImageCompression.TiffCompression.TiffCompressionJPEG
        elif self.tiff_compression == 'Packbits':
            return Metashape.ImageCompression.TiffCompression.TiffCompressionPackbits
        elif self.tiff_compression == 'Deflate':
            return Metashape.ImageCompression.TiffCompression.TiffCompressionDeflate

    @staticmethod
    def init_raster_format(format):
        if format == "TIFF/GeoTIFF":
            return Metashape.ImageFormat.ImageFormatTIFF, ".tif"
        elif format == "JPEG":
            return Metashape.ImageFormat.ImageFormatJPEG, ".jpg"
        elif format == "JPEG 2000":
            return Metashape.ImageFormat.ImageFormatJP2, ".jp2"
        elif format == "PNG":
            return Metashape.ImageFormat.ImageFormatPNG, ".png"
        elif format == "BMP":
            return Metashape.ImageFormat.ImageFormatBMP, ".bmp"
        elif format == "MTW (only for DEM)":
            return "MTW", ".mtw"
        else:
            raise TypeError("Error with format.")

    @classmethod
    def save_shapes_states(cls) -> dict:
        shapes_states = dict()

        chunk = Metashape.app.document.chunk
        for shape in chunk.shapes:
            shapes_states[shape.key] = shape.boundary_type

        return shapes_states

    @classmethod
    def upload_shapes_states(cls, shapes_states: dict):
        chunk = Metashape.app.document.chunk
        for shape in chunk.shapes:
            if shape.key in shapes_states:
                shape.boundary_type = shapes_states[shape.key]

    def __enable_users_boundary(self, enable=True):
        """
        Enables (or disables) user choice of boundary_type of shapes
        :param enable: bool. If True, enables user defined boundary_type, else sets NoBoundary
        :return:
        """
        for shape, state in self.shapes_states.items():
            shape.boundary_type = state if enable else Metashape.Shape.BoundaryType.NoBoundary

    def __set_boundaries(self):
        """
        Finds shapely Polygon (or MultiPolygon) representation of user defined export boundary. And saves shapes states
        """

        shapes_states = dict((shape, shape.boundary_type) for shape in self.chunk.shapes)
        enabled_shapes = list(filter(lambda x: x.group.enabled, shapes_states))
        outer_shapes = filter(lambda x: x.boundary_type == Metashape.Shape.BoundaryType.OuterBoundary, enabled_shapes)
        inner_shapes = filter(lambda x: x.boundary_type == Metashape.Shape.BoundaryType.InnerBoundary, enabled_shapes)

        outer_boundary = cascaded_union([self.__ps_shape2shapely_polygon(shapes) for shapes in outer_shapes])
        inner_boundary = cascaded_union([self.__ps_shape2shapely_polygon(shapes) for shapes in inner_shapes])

        boundary = outer_boundary - inner_boundary

        if boundary.is_empty:
            boundary = cascaded_union([self.__ps_shape2shapely_polygon(shape) for shape in self.shapes])

        self.shapes_states = shapes_states

        if self.buffer:
            src_polygon = ShapelyGeometry(shape=boundary, crs=self.chunk.shapes.crs.wkt)
            src_polygon.add_buffer(self.buffer)
            self.boundary = src_polygon.shape
        else:
            self.boundary = boundary

    def __get_unique_label(self, shape):
        """Finds label of shape.
        If label is empty, returns "unnamed_shape"
        If label is not unique, returns label with unique index ("unnamed_shape" --> "unnamed_shape2")
        :param shape: Metashape.Shape. Shape for processing.
        :return:
        """

        labels = self.__labels_set
        label = shape.label or 'unnamed_shape'

        if label in labels:
            counter = 2
            new_label = label + str(counter)
            while new_label in labels:
                counter += 1
                new_label = label + str(counter)
            label = new_label

        labels.add(label)
        return label

    @property
    def image_compression_attr(self):
        c = Metashape.ImageCompression()
        c.jpeg_quality = self.jpeg_quality
        c.tiff_big = self.big_tiff
        c.tiff_compression = self.tiff_compression_attr
        c.tiff_overviews = self.tiff_overviews
        c.tiff_tiled = self.tiled_tiff
        return c

    def __export_raster(self, path, progress):
        """Export DEM or orthomosaic.
        :param path. Destination path
        """

        projection = Metashape.OrthoProjection()
        projection.crs = self.crs
        translate_export = False
        add_height = False

        if self.format[0] not in self.ADDITIONAL_IMAGE_FORMATS:
            format = self.format
        else:
            format = (Metashape.ImageFormat.ImageFormatTIFF, ".tif")
            translate_export = True

        if self.source == 'dem' and self.height_correction != 0.0:
            add_height = True

        filename = os.path.splitext(os.path.basename(str(path)))[0] + format[1]
        path = os.path.join(os.path.dirname(str(path)), filename)
        kwargs = {
            "path": path,
            "image_format": format[0],
            "projection": projection,
            "resolution": self.resolution,
            "progress": progress,
            "save_world": self.write_world,
            "save_scheme": self.tile_scheme,
        }
        try:
            if isinstance(self.grid_model, Metashape.Orthomosaic):
                kwargs["save_alpha"] = self.alpha_ch
                kwargs["image_compression"] = self.image_compression_attr
                kwargs["source_data"] = Metashape.DataSource.OrthomosaicData
                kwargs["white_background"] = self.background_color
                self.chunk.exportRaster(**kwargs)
            elif isinstance(self.grid_model, Metashape.Elevation):
                kwargs["source_data"] = Metashape.DataSource.ElevationData
                kwargs["nodata_value"] = self.nodata_value
                self.chunk.exportRaster(**kwargs)
        except RuntimeError:
            traceback.print_exc()

        if self.estimated_resolution is not None:
            estimate_raster_resolution(path, mode=self.source, no_crs=self.no_crs,
                                       xres=self.estimated_resolution[0], yres=self.estimated_resolution[1])

        if translate_export:
            self.__translate_export(path, self.format[0], self.height_correction)

        if add_height and self.format[0] != "MTW":
            self.__add_height_correction(path, self.height_correction)

    def __translate_export(self, path, image_format, height_correction):
        """Raster post processing after export"""
        if image_format == "MTW":
            mtw_path = raster_to_mtw(path,
                                     no_crs=(self.mtw_crs[0] == 3),
                                     height_correction=height_correction,
                                     remove_raster=True)

            mtw_file = open(mtw_path, "r+b")
            translator = MtwCrsBuilder(mtw_file=mtw_file)
            if not self.mtw_crs:
                raise ValueError("CRS for MTW was not set.")

            if self.mtw_crs[0] == 1 and self.mtw_crs[2]:
                translator.create_gsk_zone(vertical_datum=self.mtw_crs[1], zone=self.mtw_crs[2])
            elif self.mtw_crs[0] == 2:
                translator.create_geo_gsk(vertical_datum=self.mtw_crs[1])
            else:
                translator.create_no_crs()
            mtw_file.close()

    @staticmethod
    def __add_height_correction(path, value):
        raster = gdal.Open(path, gdal.GA_Update)
        data = raster.GetRasterBand(1).ReadAsArray()
        nodata = raster.GetRasterBand(1).GetNoDataValue()
        data[data != nodata] += value
        raster.GetRasterBand(1).WriteArray(data)
        raster.GetRasterBand(1).SetNoDataValue(nodata)
        del raster

    @staticmethod
    def __ps_shape2shapely_polygon(ps_shape):
        """
        Converts Metashape.Shape() instance to shapely Polygon.
        :param ps_shape: Metashape.Shape() instance.
        :return: shapely.geom.Polygon
        """
        polygon = Polygon([v for v in flatten_list(ps_shape.geometry.coordinates)])
        return polygon

    def __shapely_polygon2ps_shapes(self, shapely_polygon):
        """
        Converts shapely.geom.Polygon instance to list of Metashape.Shape() instances with specified boundary type.
        :param shapely_polygon:
        :return:
        """
        def create(linering, boundary):
            coords = [Metashape.Vector(vertex) for vertex in linering.coords]
            shape = create_shape(coords, label='temp', group=self.__tmp_shapes_group)
            shape.boundary_type = boundary
            return shape

        shapes = [create(shapely_polygon.exterior, Metashape.Shape.BoundaryType.OuterBoundary)]

        for interior in shapely_polygon.interiors:
            shapes.append(create(interior, Metashape.Shape.BoundaryType.InnerBoundary))

        return shapes

    def __create_source_polygon(self, shape):
        """
        Creates export source shapely.geom.Polygon instance with predefined buffer.
        :param shape: Metashape.Shape() instance
        :return: shapely.geom.Polygon() instance
        """
        temp_group = self.chunk.shapes.addGroup()
        temp_shape = create_shape(vertices=flatten_list(shape.geometry.coordinates), group=temp_group)

        src_polygon = ShapeGeometry(temp_shape, self.chunk.shapes.crs.proj4)
        src_polygon.add_buffer(self.buffer)
        buffered_polygon = ShapeGeometry.convert_to_shapely_geometry(src_polygon.shape)

        self.chunk.shapes.remove(temp_shape)
        self.chunk.shapes.remove(temp_group)

        return buffered_polygon

    def __create_export_shapes(self, shape):
        """
        Creates list of shapes for exporting by main export shape
        :param shape: Metashape.Shape() instance
        :return: list of Metashape.Shape() instances
        """
        src_polygon = self.__create_source_polygon(shape)
        if not src_polygon.is_valid:
            src_polygon = src_polygon.buffer(0)

        dst_polygon = src_polygon.intersection(self.boundary) if self.boundary else src_polygon

        if dst_polygon.geom_type == 'Polygon':
            return self.__shapely_polygon2ps_shapes(dst_polygon)
        elif dst_polygon.geom_type == 'MultiPolygon':
            dst_shapes = []
            for polygon in dst_polygon:
                dst_shapes.extend(self.__shapely_polygon2ps_shapes(polygon))
            return dst_shapes
        elif dst_polygon.is_empty:
            return None
        else:
            raise Exception("Unexpected error! Shape key is {}".format(shape.key))

    def __export_by_shape(self, shape, progress):
        """Provides export for single shape.
        :param shape: Metashape.Shape. Shape for processing.
        """

        label = self.__get_unique_label(shape)
        export_path = self.path / (label+'.tif')
        export_shapes = self.__create_export_shapes(shape)

        if export_shapes:
            print(export_path)
            self.__export_raster(export_path, progress)
            self.chunk.shapes.remove(export_shapes)
            return export_path
        else:
            print("Empty intersection. Shape key is {}".format(shape.key))
            return None

    def export(self, progress=lambda: None, shapes_progress=lambda x: x, process_result: (None, Callable) = None):
        """Starts exporting
        :param progress: callback function
        :param shapes_progress: callback function without Metashape API.
        :param process_result: (None, Callable). Process export file by custom function.
        :return:
        """
        def progress_func(val):
            progress((i+val/100)*100/total)

        self.__enable_users_boundary(False)

        shapes = self.chunk.shapes
        self.__tmp_shapes_group = self.chunk.shapes.addGroup()
        self.__tmp_shapes_group.label = 'Temporary shapes group'

        total = len(self.shapes)
        i = 0
        for i, shape in enumerate(self.shapes):
            shapes_progress(i / total * 100)
            export_path = self.__export_by_shape(shape, progress_func)
            if process_result is not None and export_path is not None and os.path.exists(export_path):
                try:
                    process_result(str(export_path))
                except:
                    raise AssertionError(export_path)

        shapes.remove(self.__tmp_shapes_group)
        self.__enable_users_boundary(True)
        progress(100)


def estimate_raster_resolution(path, mode, no_crs,
                               black_boundary=False, remove_raster=True, xres=None, yres=None, improve_tfw=True):
    """Set raster resolution to user value and other options."""

    temp_path = os.path.join(os.path.dirname(path),
                             os.path.splitext(os.path.basename(path))[0] + "_new" + os.path.splitext(os.path.basename(path))[1])

    source_ds = gdal.Open(path, gdal.GA_ReadOnly)
    driver = source_ds.GetDriver()

    geotransform = source_ds.GetGeoTransform()
    if all([xres, yres]):
        geotransform = (geotransform[0], xres, geotransform[2], geotransform[3], geotransform[4], -yres)

    estimated_ds = driver.Create(temp_path,
                                 xsize=source_ds.RasterXSize + 2 if black_boundary else source_ds.RasterXSize,
                                 ysize=source_ds.RasterYSize + 2 if black_boundary else source_ds.RasterYSize,
                                 bands=source_ds.RasterCount,
                                 eType=gdal.GDT_Byte if mode == "ortho" else gdal.GDT_Float32
                                 )

    estimated_ds.SetGeoTransform(geotransform)
    if not no_crs:
        estimated_ds.SetProjection(source_ds.GetProjection())

    for band_number in range(1, source_ds.RasterCount + 1):
        data = source_ds.GetRasterBand(band_number).ReadAsArray()
        if black_boundary:
            data = create_black_pixel_boundary(data, source_ds.RasterXSize, source_ds.RasterYSize)

        estimated_ds.GetRasterBand(band_number).WriteArray(data)

    del source_ds
    del estimated_ds

    if improve_tfw:
        tfw_file = os.path.join(os.path.dirname(path), os.path.splitext(os.path.basename(path))[0] + ".tfw")
        with open(tfw_file, 'w') as file:
            text = "\n".join([str(i) for i in geotransform]) + '\n'
            file.write(text)

    if remove_raster:
        os.remove(path)
        os.rename(temp_path, path)


def create_black_pixel_boundary(source, xsize, ysize):
    """Create black boundary for raster with size = 1 pixel"""

    h_black = np.array([0 for _ in range(xsize)])
    v_black = np.array([[0 for _ in range(ysize + 2)]])

    source = np.vstack((source, h_black))  # add bottom line
    source = np.vstack((h_black, source))  # add top line
    source = np.concatenate((source, v_black.T), axis=1)  # add right line
    source = np.concatenate((v_black.T, source), axis=1)  # add left line

    return source


if __name__ == '__main__':
    pass
