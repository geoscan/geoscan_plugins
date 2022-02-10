"""Contour tools for Agisoft Metashape

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
import pyclipper
from shutil import copy2

import PhotoScan as ps
import cv2
import numpy as np
from PySide2.QtCore import *
from PySide2.QtWidgets import *

from common.utils.bridge import real_vertices
from common.utils.ui import show_error, ProgressBar


def project_contour_to_camera(s, cam):
    c = ps.app.document.chunk.sensors[0].calibration
    vertices = real_vertices(s)
    pixels = [cam.project(v) for v in vertices]
    if None in pixels:
        return []
    m = max(-int(np.min(pixels)), 0)
    pixels = [(int(p.x) + m, int(p.y) + m) for p in pixels]
    m2 = np.max(pixels)
    if m2 > 4.6e+18:
        return []
    pc = pyclipper.Pyclipper()
    clip = ((m, m), (m, c.height + m), (c.width + m, c.height + m), (c.width + m, m))
    subj = pixels

    pc.AddPath(clip, pyclipper.PT_CLIP, True)
    pc.AddPath(subj, pyclipper.PT_SUBJECT, True)

    solution = pc.Execute(pyclipper.CT_INTERSECTION, pyclipper.PFT_EVENODD, pyclipper.PFT_EVENODD)

    res_pixels = []
    for path in solution:
        for x, y in path:
            res_pixels.append((x - m, y - m))
    return res_pixels


def hide_contour(cam, contour, fraction=5):
    img = np.fromstring(cam.photo.image().tostring(),  dtype=np.uint8)
    w, h = cam.sensor.calibration.width, cam.sensor.calibration.height
    img = img.reshape((h, w, 3))
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    mask = np.zeros(img.shape[:-1], dtype=np.uint8)
    cv2.drawContours(mask, [np.array(contour)], -1, 255, -1)
    mask = mask.astype(np.bool)
    mask = np.dstack((mask, mask, mask))
    img2 = cv2.resize(img, (0, 0), fx=1./(2**fraction), fy=1./(2**fraction))
    img2 = cv2.resize(img2, (img.shape[1], img.shape[0]))
    return np.where(mask, img2, img)

class GenericContourOperation:
    def __init__(self):
        self.progress_text = "set this text"

    def project_onto_cameras(self):
        """
        Find cam with contours
        :return: nothing
        """
        selected_contours = (s for s in ps.app.document.chunk.shapes if s.selected)
        for cont in selected_contours:
            try:
                if cont.boundary_type == ps.Shape.BoundaryType.InnerBoundary:
                    invert_inside = True
                else:
                    invert_inside = False
            except StopIteration:
                show_error(_("Contour not selected"), _("Please select contour"))
                return
            if not cont.geometry.is_3d:
                show_error(_("No height for contour"), _("Please add heights to selected contour"))
                return
            pb = ProgressBar(self.progress_text)
            for idx, cam in enumerate(ps.app.document.chunk.cameras):
                pb.update((idx / len(ps.app.document.chunk.cameras)) * 100)
                contour = project_contour_to_camera(cont, cam)
                if len(contour):
                    self.process_contour(cam, contour, invert_inside)

    def process_contour(self, cam, contour, invert_inside):
        raise NotImplementedError


class MakeMasks(GenericContourOperation):
    def __init__(self):
        super().__init__()
        self.progress_text = _("Creating masks from contour")

    def process_contour(self, cam, contour, invert_inside):
        """
        Create masks for every cam with contour
        :param cam: camera instance
        :param contour: contour instance
        :param invert_inside: outer(False) or inner(True) boundary
        :return: nothing
        """
        w, h = cam.sensor.calibration.width, cam.sensor.calibration.height
        if cam.mask is None:
            cam.mask = ps.Mask()
            if invert_inside:
                mask = np.zeros((h, w), dtype=np.uint8)
                mask.fill(255)
                cv2.drawContours(mask, [np.array(contour)], -1, 0, -1)
            else:
                mask = np.zeros((h, w), dtype=np.uint8)
                cv2.drawContours(mask, [np.array(contour)], -1, 255, -1)
        else:
            mask_im = cam.mask.image()
            mask_old = np.frombuffer(mask_im.tostring(), dtype=np.uint8)
            if mask_old.size == 12000000: #DJI
                mask_old = mask_old.reshape(3000, 4000)
            else: #our photos
                mask_old = mask_old.reshape(4000, 6000)
            if invert_inside:
                mask_new = np.zeros((h, w), dtype=np.uint8)
                mask_new.fill(255)
                cv2.drawContours(mask_new, [np.array(contour)], -1, 0, -1)
                mask = mask_old * mask_new

            else:
                mask_new = np.zeros((h, w), dtype=np.uint8)
                cv2.drawContours(mask_new, [np.array(contour)], -1, 255, -1)
                mask = mask_old * mask_new
        im = ps.Image.fromstring(mask.tostring(), w, h, 'L')
        cam.mask.setImage(im)


class HideContourDialog(QWidget, GenericContourOperation):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.progress_text = _("Hiding all objects")
        self.backuped = set()

        layout = QVBoxLayout()
        label = QLabel(_("Fraction of coarsen: "))

        slider_layout = QHBoxLayout()
        smin = QLabel("2")
        smax = QLabel("8")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(2, 8)
        self.slider.setValue(6)
        slider_layout.addWidget(smin)
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(smax)

        self.scurr = QLabel(_("coarsen by: " + "6"))

        # self.rewrite_backup_checkbox = QCheckBox()
        # self.rewrite_backup_checkbox.setText(_("Rewrite backup?"))
        # self.rewrite_backup_checkbox.setChecked(False)

        apply_button = QPushButton(_("Apply coarsen"))

        layout.addWidget(label)
        layout.addLayout(slider_layout)
        layout.addWidget(self.scurr)
        # layout.addWidget(self.rewrite_backup_checkbox)
        layout.addWidget(apply_button)
        self.setLayout(layout)
        self.resize(self.minimumSizeHint())

        self.slider.valueChanged.connect(lambda val: self.scurr.setText(_("coarsen by: ") + str(val)))
        apply_button.clicked.connect(lambda: self.project_onto_cameras())

    def backup_photo(self, cam):
        # pass
        path = os.path.normpath(cam.photo.path)
        d = os.path.dirname(path)
        dd = os.path.split(d)[-1]
        uplevel = os.path.dirname(d)
        original = os.path.normpath(os.path.join(uplevel, 'original_' + dd))
        backup_path = os.path.normpath(os.path.join(original, os.path.split(path)[-1]))
        if not os.path.exists(backup_path):
            os.makedirs(original, exist_ok=True)
            copy2(path, backup_path)

    def process_contour(self, cam, contour):
        try:
            self.backup_photo(cam)
        except:
            import traceback
            traceback.print_exc()
            return
        res_image = hide_contour(cam, contour, int(self.slider.value() - 1))
        cv2.imwrite(os.path.normpath(cam.photo.path), res_image)

    @staticmethod
    def hide_contour_window(trans):
        trans.install()
        _ = trans.gettext
        app = QApplication.instance()
        win = app.activeWindow()
        if ps.app.document.chunk is None:
            show_error(_("Error"), _("Please open document which you want to work with!"))
            return
        dialog = QDialog(win)
        HideContourDialog(dialog)
        dialog.show()
