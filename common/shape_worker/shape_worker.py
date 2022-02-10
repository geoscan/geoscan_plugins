"""Common scripts, classes and functions

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

import PhotoScan
import PhotoScan as ps

import cv2
import numpy as np
import pyclipper

from common.utils.bridge import chunk_crs_to_geocentric, real_vertices_in_shape_crs, real_vertices, camera_coordinates_to_geocentric


def init_shapes(chunk=None, crs=None):
    if chunk is None:
        chunk = PhotoScan.app.document.chunk  # current chunk if chunk not specify

    if chunk.shapes is None:
        chunk.shapes = PhotoScan.Shapes()
        if crs is not None:
            chunk.shapes.crs = crs


def create_shape(vertices: list, chunk: PhotoScan.Chunk = None, label: str = "", group: PhotoScan.ShapeGroup = None,
                 z_coord: float = None, shape_type: str = 'Polygon', boundary_type: str = 'NoBoundary'):
    """
    Create shape
    @param vertices: List of shape vertices of dimensions [n][2] or [n][3]. if shape has dimension [n][2]
        the z coord can be defined as 'z_coord' param
    @param chunk: destination chunk (optional). is doesn't set, use current chunk
    @param label: shape label (optional)
    @param group: shape group in PhotoScan (optional)
    @param z_coord: use it if shape doesn't have third coord (optional)
    @param shape_type: must be one of "Point", "Polygon" (default) or "Polyline"
    @param boundary_type: must be one of "InnerBoundary", "NoBoundary" (default) or OuterBoundary
    """
    if chunk is None:
        chunk = PhotoScan.app.document.chunk  # current chunk if chunk not specify

    shp = chunk.shapes.addShape()
    shp.label = label
    if len(vertices[0]) < 3:
        if z_coord is not None:
            shp_vertices = [[pt[0], pt[1], z_coord] for pt in vertices]
        else:
            shp_vertices = [[pt[0], pt[1]] for pt in vertices]
    else:
        shp_vertices = [[pt[0], pt[1], pt[2]] for pt in vertices]

    if group is not None:
        shp.group = group

    shp_type_classes = {
        "Point": PhotoScan.Geometry.Point,
        "Polygon": PhotoScan.Geometry.Polygon,
        "Polyline": PhotoScan.Geometry.LineString,
    }
    geometry_class = shp_type_classes[shape_type]
    shp.geometry = geometry_class(shp_vertices)

    shp.boundary_type = PhotoScan.Shape.BoundaryType.values[boundary_type]

    return shp


def flatten_list(input_list):
    if not input_list:
        return []
    output_list = []
    for i in input_list:
        if not isinstance(i, list):
            output_list.append(i)
        else:
            output_list += flatten_list(i)
    return output_list


def create_layer(shapes: list, label: str, chunk: PhotoScan.Chunk = None,
                 is_enabled: bool = True, show_labels: bool = True,
                 z_coord: float = None, shape_type: str = 'Polygon', boundary_type: str = 'NoBoundary'):
    """ Equal to create_shape, but for list of Metashape.Shape objects"""

    if chunk is None:
        chunk = PhotoScan.app.document.chunk  # current chunk if chunk not specify

    group = create_group(label=label, is_enabled=is_enabled, show_labels=show_labels)

    for shape in shapes:
        create_shape(vertices=shape.vertices, chunk=chunk, label=shape.label, group=group,
                     z_coord=z_coord, shape_type=shape_type, boundary_type=boundary_type)


def rm_shapes_in_shape(shape):
    shp = np.array([[pt.x, pt.y] for pt in shape.vertices], dtype=np.float32)

    for sh in PhotoScan.app.document.chunk.shapes.shapes:
        if len(sh.vertices) < 3:
            continue
        if cv2.pointPolygonTest(shp, (sh.vertices[0][0], sh.vertices[0][1]), False) > 0:
            PhotoScan.app.document.chunk.shapes.remove(sh)


def aver_shapes_z(shapes):
    for shp in shapes:
        level = np.mean([pt.z for pt in shp.vertices])
        print(level)
        for i, pt in enumerate(shp.vertices):
            shp.vertices[i] = PhotoScan.Vector([pt.x, pt.y, level])


def get_selected_shapes():
    shapes = []
    for sh in PhotoScan.app.document.chunk.shapes.shapes:
        if sh.selected:
            shapes.append(sh)
    return shapes


def copy_shape(shape, chunk=None):
    if chunk is None:
        shp = PhotoScan.app.document.chunk.shapes.addShape()
    else:
        chunk.shapes = PhotoScan.Shapes()
        chunk.shapes.crs = PhotoScan.app.document.chunk.crs
        shp = chunk.shapes.addShape()
    shp.label = ""
    shp.has_z = True
    shp.vertices = real_vertices_in_shape_crs(shape)
    shp.group = shape.group
    shp.type = shape.type
    shp.has_z = shape.has_z

    return shp


def move_shapes_to_group(shapes, group):
    for sh in shapes:
        sh.group = group


def increase_contour(cnt, val):
    x, y, w, h = cv2.boundingRect(cnt)
    res = np.zeros_like(cnt)
    offset = np.array([x, y])
    additional_offset = np.array([val, val])
    img = np.zeros((h + val * 2, w + val * 2), dtype=np.uint8)
    if x > 0 and y > 0:
        for i, p in enumerate(cnt):
            res[i] = p - offset + additional_offset

    cv2.drawContours(img, [res], -1, 255, cv2.FILLED)
    kernel = np.ones((val, val), np.uint8)
    img = cv2.dilate(img, kernel, iterations=1)
    _, res, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(res) < 1:
        return cnt
    for i, p in enumerate(res[0]):
        res[0][i] = p + offset - additional_offset
    return res[0]


def decrease_contour(cnt, val):
    x, y, w, h = cv2.boundingRect(cnt)
    res = np.zeros_like(cnt)
    offset = np.array([x, y])
    additional_offset = np.array([val + 1, val + 1])
    img = np.zeros((h + (val + 1) * 2, w + (val + 1) * 2), dtype=np.uint8)
    if x > 0 and y > 0:
        for i, p in enumerate(cnt):
            res[i] = p - offset + additional_offset

    cv2.drawContours(img, [res], -1, 255, cv2.FILLED)
    kernel = np.ones((val, val), np.uint8)
    img = cv2.erode(img, kernel, iterations=1)
    _, res, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(res) < 1:
        return cnt
    for i, p in enumerate(res[0]):
        res[0][i] = p + offset - additional_offset
    return res[0]


def scale_contour(cnt, val):
    if val == 0:
        return cnt
    elif val > 0:
        return increase_contour(cnt, val)
    elif val < 0:
        return decrease_contour(cnt, -1 * val)


def shape_to_img_coords(shape_vertices, transform):
    """
    Transform shape to image coordinates
    :param shape_vertices: shape_vertices
    :param transform: gdal transform
    :return: new transformed shape
    """
    x, dx, a1, y, a2, dy = transform
    return np.array([[int((pt[0] - x) / dx), int((pt[1] - y) / dy)] for pt in shape_vertices], dtype=np.uint32)


def copy_shapes_against_chunks(transmitter, receiver):
    """
    Copy shapes against two chunks
    :param transmitter: donor chunk
    :param receiver: receiver chunk
    :return: none
    """
    for sh in transmitter.shapes:
        copy_shape(sh, receiver)


def get_shapes_by_group(group):
    """
    Get shapes by shapes group
    :param group: Photoscan.ShapeGroup. Shapes group
    :return: List of shapes
    """
    res = []
    for sh in PhotoScan.app.document.chunk.shapes.shapes:
        if sh.group == group:
            res.append(sh)

    return res


def get_shapes_by_group_id(id_):
    """
    Get shapes by shapes group id
    :param id_: Group index
    :return: List of shapes
    """
    grp = PhotoScan.app.document.chunk.shapes.groups[id_]

    return get_shapes_by_group(grp)


def delete_shapes_by_group_key(group_key):
    shapes = PhotoScan.app.document.chunk.shapes.shapes

    for shape in shapes:
        if shape.group.key == group_key:
            PhotoScan.app.document.chunk.shapes.remove(shape)


def create_group(label: str="", is_enabled: bool=1, show_labels: bool=False):
    init_shapes()

    group = PhotoScan.app.document.chunk.shapes.addGroup()
    group.label = label
    group.enabled = is_enabled
    group.show_labels = show_labels
    return group


def delete_group(group, with_shapes: bool=False):
    if with_shapes:
        delete_shapes_by_group_key(group.key)

    PhotoScan.app.document.chunk.shapes.remove(group)


def modify_contours_offset(shapes, offset):
    crs = ps.app.document.chunk.shapes.crs
    for c in shapes:
        vertices = list(map(camera_coordinates_to_geocentric, real_vertices(c)))
        flat_vertices = [(v.x * 100, v.y * 100) for v in vertices]
        pco = pyclipper.PyclipperOffset()
        pco.AddPath(flat_vertices, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        res = pco.Execute(offset)
        c.selected = False
        for poly in res:
            new_vertices = []
            for vertex in poly:
                idx = (np.linalg.norm(np.array(flat_vertices) - np.array(vertex), axis=1)).argmin()
                z = list(vertices)[idx].z
                v = ps.Vector([vertex[0] / 100., vertex[1] / 100., z])
                new_vertices.append(crs.project(v))
            s = ps.app.document.chunk.shapes.addShape()
            s.vertices = new_vertices
            s.has_z = True
            s.type = c.type
            s.selected = True
    # ps.app.document.chunk.remove(shapes)


def duplicate_contours(shapes):
    res = []
    for c in shapes:
        s = ps.app.document.chunk.shapes.addShape()
        s.label = c.label + " dup"
        s.has_z = c.has_z
        s.type = c.type
        s.vertices = real_vertices_in_shape_crs(c)
        s.selected = True
        c.selected = False
        res.append(s)
    return res


def copy_contours_on_different_height(shapes, delta_h):
    shapes = duplicate_contours(shapes)
    for c in shapes:
        vertices = real_vertices_in_shape_crs(c)
        c.vertices = [ps.Vector([v.x, v.y, v.z + delta_h / 100.]) for v in vertices]


if __name__ == "__main__":
    ps_chunk = PhotoScan.app.document.chunk

    copy_shapes_against_chunks(ps_chunk, PhotoScan.app.document.chunks[2])
    # rm_shapes_in_shape(get_selected_shape())
    #
    # f = open("D://projects//shp.txt", 'w')
    #
    # for pt in shp.vertices:
    #     f.write("{} {}\n".format(pt.x, pt.y))
    #
    # f.close()
    # aver_shapes_z(ps_chunk.shapes.shapes)
    #
    # group = ps_chunk.shapes.groups[2]
    #
    # move_shapes_to_group([ shp for shp in ps_chunk.shapes.shapes if shp.group == ps_chunk.shapes.groups[0]], group)
