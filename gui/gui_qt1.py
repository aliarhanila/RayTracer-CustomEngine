import sys
import numpy as np
import math
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QColorDialog, QFormLayout, QDoubleSpinBox, QMessageBox
)
from PyQt5.QtGui import QImage, QPixmap, QColor
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal

from render import renderer

class RenderThread(QThread):
    rendered = pyqtSignal(np.ndarray)

    def __init__(self, width, height, objects, lights, camera_pos, camera_dir, background_color, parent=None):
        super().__init__(parent)
        self.width = width
        self.height = height
        self.objects = objects
        self.lights = lights
        self.camera_pos = camera_pos
        self.camera_dir = camera_dir
        self.background_color = background_color
        self.frame = 0
        self.running = True

    def run(self):
        while self.running:
            self.frame += 1
            for light in self.lights:
                if light.get('speed', 0) != 0:
                    angle = self.frame * 0.05 * light['speed'] + light.get('phase', 0)
                    radius = np.linalg.norm(light['pos'][[0, 2]])
                    light['pos'][0] = radius * np.cos(angle)
                    light['pos'][2] = radius * np.sin(angle)

            img_array = renderer.render(
                self.width, self.height,
                self.objects, self.lights,
                self.camera_pos, self.camera_dir, self.background_color
            )

            self.rendered.emit(img_array)
            self.msleep(0)

    def stop(self):
        self.running = False
        self.wait()

class RayTracerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ray Tracer GUI - C Engine")
        
        self.WIDTH = 1600
        self.HEIGHT = 900
        k = 1
        self.RENDER_WIDTH = self.WIDTH // k
        self.RENDER_HEIGHT = self.HEIGHT // k
        
        self.camera_pos = np.array([0.0, 0.0, -3.0])
        self.camera_dir = np.array([0.0, 0.0, 1.0])
        self.background_color = np.array([0.05, 0.05, 0.05])
        
        self.yaw = 0.0
        self.pitch = 0.0
        self.looking = False
        self.keys = {'W': False, 'A': False, 'S': False, 'D': False, 'Space': False, 'Shift': False}

        self.objects = []
        self.lights = []
        self.selected_obj_index = None
        self.selected_light_index = None

        self.init_ui()
        self.start_render_thread()
        self.start_fps_timer()
        
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.game_timer = QTimer()
        self.game_timer.timeout.connect(self.update_movement)
        self.game_timer.start(16)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.last_mouse_pos = event.pos()
            self.looking = True

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self.looking = False

    def mouseMoveEvent(self, event):
        if self.looking:
            dx = event.x() - self.last_mouse_pos.x()
            dy = event.y() - self.last_mouse_pos.y()
            self.last_mouse_pos = event.pos()

            sensitivity = 0.005
            self.yaw += dx * sensitivity
            self.pitch += dy * sensitivity 

            self.pitch = max(-1.5, min(1.5, self.pitch))

            dir_x = math.cos(self.pitch) * math.sin(self.yaw)
            dir_y = -math.sin(self.pitch)
            dir_z = math.cos(self.pitch) * math.cos(self.yaw)
            
            self.camera_dir = np.array([dir_x, dir_y, dir_z])

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_W: self.keys['W'] = True
        elif event.key() == Qt.Key_S: self.keys['S'] = True
        elif event.key() == Qt.Key_A: self.keys['A'] = True
        elif event.key() == Qt.Key_D: self.keys['D'] = True
        elif event.key() == Qt.Key_Space: self.keys['Space'] = True
        elif event.key() == Qt.Key_Shift: self.keys['Shift'] = True

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_W: self.keys['W'] = False
        elif event.key() == Qt.Key_S: self.keys['S'] = False
        elif event.key() == Qt.Key_A: self.keys['A'] = False
        elif event.key() == Qt.Key_D: self.keys['D'] = False
        elif event.key() == Qt.Key_Space: self.keys['Space'] = False
        elif event.key() == Qt.Key_Shift: self.keys['Shift'] = False

    def update_movement(self):
        speed = 0.05
        
        forward = np.array([self.camera_dir[0], 0, self.camera_dir[2]])
        norm = np.linalg.norm(forward)
        if norm > 0:
            forward = forward / norm
            
        right = np.cross(np.array([0, 1, 0]), forward)

        if self.keys['W']: self.camera_pos += forward * speed
        if self.keys['S']: self.camera_pos -= forward * speed
        if self.keys['A']: self.camera_pos -= right * speed
        if self.keys['D']: self.camera_pos += right * speed
        if self.keys['Space']: self.camera_pos[1] += speed
        if self.keys['Shift']: self.camera_pos[1] -= speed

        if hasattr(self, 'render_thread'):
            self.render_thread.camera_pos = self.camera_pos.copy()
            self.render_thread.camera_dir = self.camera_dir.copy()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        self.image_label = QLabel()
        self.image_label.setFixedSize(self.WIDTH, self.HEIGHT)
        main_layout.addWidget(self.image_label)

        control_panel = QVBoxLayout()
        main_layout.addLayout(control_panel)

        # --- OBJELER BÖLÜMÜ ---
        control_panel.addWidget(QLabel("Küreler ve Düzlemler:"))
        self.obj_list = QListWidget()
        control_panel.addWidget(self.obj_list)
        self.obj_list.currentRowChanged.connect(self.on_obj_selected)

        self.obj_params_layout = QFormLayout()
        control_panel.addLayout(self.obj_params_layout)

        self.obj_pos_x = QDoubleSpinBox(); self.obj_pos_x.setRange(-10, 10)
        self.obj_pos_y = QDoubleSpinBox(); self.obj_pos_y.setRange(-10, 10)
        self.obj_pos_z = QDoubleSpinBox(); self.obj_pos_z.setRange(-10, 10)
        self.obj_radius = QDoubleSpinBox(); self.obj_radius.setRange(0.01, 5); self.obj_radius.setSingleStep(0.01)

        self.obj_pos_x.valueChanged.connect(self.update_selected_obj)
        self.obj_pos_y.valueChanged.connect(self.update_selected_obj)
        self.obj_pos_z.valueChanged.connect(self.update_selected_obj)
        self.obj_radius.valueChanged.connect(self.update_selected_obj)

        self.obj_color_btn = QPushButton("Renk Seç")
        self.obj_color_btn.clicked.connect(self.choose_obj_color)
        
        self.obj_delete_btn = QPushButton("Seçili Objeyi Sil")
        self.obj_delete_btn.setStyleSheet("background-color: #ff4c4c; color: white;")
        self.obj_delete_btn.clicked.connect(self.delete_object)

        self.obj_params_layout.addRow("Pozisyon X:", self.obj_pos_x)
        self.obj_params_layout.addRow("Pozisyon Y:", self.obj_pos_y)
        self.obj_params_layout.addRow("Pozisyon Z:", self.obj_pos_z)
        self.obj_params_layout.addRow("Yarıçap:", self.obj_radius)
        self.obj_params_layout.addRow("Renk:", self.obj_color_btn)
        self.obj_params_layout.addRow("", self.obj_delete_btn) # Silme butonu

        obj_buttons_layout = QHBoxLayout()
        self.obj_add_btn = QPushButton("Küre Ekle")
        self.obj_add_btn.clicked.connect(self.add_object)
        self.plane_add_btn = QPushButton("Düzlem Ekle")
        self.plane_add_btn.clicked.connect(self.add_plane)
        obj_buttons_layout.addWidget(self.obj_add_btn)
        obj_buttons_layout.addWidget(self.plane_add_btn)
        control_panel.addLayout(obj_buttons_layout)

        control_panel.addSpacing(20)

        # --- IŞIKLAR BÖLÜMÜ ---
        control_panel.addWidget(QLabel("Işıklar:"))
        self.light_list = QListWidget()
        control_panel.addWidget(self.light_list)
        self.light_list.currentRowChanged.connect(self.on_light_selected)

        self.light_params_layout = QFormLayout()
        control_panel.addLayout(self.light_params_layout)

        self.light_pos_x = QDoubleSpinBox(); self.light_pos_x.setRange(-10, 10)
        self.light_pos_y = QDoubleSpinBox(); self.light_pos_y.setRange(-10, 10)
        self.light_pos_z = QDoubleSpinBox(); self.light_pos_z.setRange(-10, 10)
        self.light_radius = QDoubleSpinBox(); self.light_radius.setRange(0.01, 5); self.light_radius.setSingleStep(0.01)
        self.light_power = QDoubleSpinBox(); self.light_power.setRange(0.0, 50.0); self.light_power.setSingleStep(0.5) # GÜÇ AYARI
        self.light_speed = QDoubleSpinBox(); self.light_speed.setRange(0, 10); self.light_speed.setSingleStep(0.1)
        self.light_phase = QDoubleSpinBox(); self.light_phase.setRange(0, 2*math.pi); self.light_phase.setSingleStep(0.1)

        self.light_pos_x.valueChanged.connect(self.update_selected_light)
        self.light_pos_y.valueChanged.connect(self.update_selected_light)
        self.light_pos_z.valueChanged.connect(self.update_selected_light)
        self.light_radius.valueChanged.connect(self.update_selected_light)
        self.light_power.valueChanged.connect(self.update_selected_light)
        self.light_speed.valueChanged.connect(self.update_selected_light)
        self.light_phase.valueChanged.connect(self.update_selected_light)

        self.light_color_btn = QPushButton("Renk Seç")
        self.light_color_btn.clicked.connect(self.choose_light_color)

        self.light_delete_btn = QPushButton("Seçili Işığı Sil")
        self.light_delete_btn.setStyleSheet("background-color: #ff4c4c; color: white;")
        self.light_delete_btn.clicked.connect(self.delete_light)

        self.light_params_layout.addRow("Pozisyon X:", self.light_pos_x)
        self.light_params_layout.addRow("Pozisyon Y:", self.light_pos_y)
        self.light_params_layout.addRow("Pozisyon Z:", self.light_pos_z)
        self.light_params_layout.addRow("Yarıçap:", self.light_radius)
        self.light_params_layout.addRow("Işık Gücü:", self.light_power) # Arayüze eklendi
        self.light_params_layout.addRow("Renk:", self.light_color_btn)
        self.light_params_layout.addRow("Dönme Hızı:", self.light_speed)
        self.light_params_layout.addRow("Faz (rad):", self.light_phase)
        self.light_params_layout.addRow("", self.light_delete_btn) # Silme butonu

        self.light_add_btn = QPushButton("Işık Ekle")
        self.light_add_btn.clicked.connect(self.add_light)
        control_panel.addWidget(self.light_add_btn)

        self.update_obj_list()
        self.update_light_list()

    # --- LİSTE GÜNCELLEMELERİ VE SİLME İŞLEMLERİ ---
    
    def update_obj_list(self):
        for obj in self.objects:
            if 'type' not in obj:
                obj['type'] = 'sphere'

        self.obj_list.clear()
        for i, obj in enumerate(self.objects):
            label = f"{obj['type'].capitalize()} {i}"
            if obj['type'] == 'sphere':
                label += f": Pos({obj['center'][0]:.2f},{obj['center'][1]:.2f},{obj['center'][2]:.2f}) R:{obj['radius']:.2f}"
            elif obj['type'] == 'plane':
                label += f": Point({obj['point'][0]:.2f},{obj['point'][1]:.2f},{obj['point'][2]:.2f})"
            self.obj_list.addItem(label)

    def delete_object(self):
        if self.selected_obj_index is not None and 0 <= self.selected_obj_index < len(self.objects):
            self.objects.pop(self.selected_obj_index)
            self.selected_obj_index = None
            self.update_obj_list()
            self.setFocus() # Odağı ana pencereye geri ver

    def delete_light(self):
        if self.selected_light_index is not None and 0 <= self.selected_light_index < len(self.lights):
            self.lights.pop(self.selected_light_index)
            self.selected_light_index = None
            self.update_light_list()
            self.setFocus()

    def add_object(self):
        new_obj = {
            'type': 'sphere',
            'center': np.array([0.0, 0.0, 1.0]),
            'radius': 0.5,
            'color': np.array([1.0, 1.0, 1.0]),
            'reflectivity': 0.8  
            }
        self.objects.append(new_obj)
        self.update_obj_list()

    def add_plane(self):
        new_obj = {
            'type': 'plane',
            'point': np.array([0.0, -0.5, 0.0]),
            'normal': np.array([0.0, 1.0, 0.0]),
            'color': np.array([0.5, 0.5, 0.5]),
            'reflectivity': 0.8  
        }
        self.objects.append(new_obj)
        self.update_obj_list()

    def update_light_list(self):
        self.light_list.clear()
        for i, light in enumerate(self.lights):
            p = light.get('power', 1.0)
            self.light_list.addItem(f"Işık {i}: Pos({light['pos'][0]:.2f},{light['pos'][1]:.2f},{light['pos'][2]:.2f}) Güç:{p:.1f}")

    def on_obj_selected(self, index):
        if index < 0 or index >= len(self.objects):
            self.selected_obj_index = None
            return
        self.selected_obj_index = index
        obj = self.objects[index]

        self.obj_pos_x.blockSignals(True)
        self.obj_pos_y.blockSignals(True)
        self.obj_pos_z.blockSignals(True)
        self.obj_radius.blockSignals(True)

        self.obj_pos_x.setValue(obj['center'][0])
        self.obj_pos_y.setValue(obj['center'][1])
        self.obj_pos_z.setValue(obj['center'][2])
        self.obj_radius.setValue(obj.get('radius', 0.5))

        self.obj_pos_x.blockSignals(False)
        self.obj_pos_y.blockSignals(False)
        self.obj_pos_z.blockSignals(False)
        self.obj_radius.blockSignals(False)

    def update_selected_obj(self):
        if self.selected_obj_index is None:
            return
        obj = self.objects[self.selected_obj_index]
        obj['center'][0] = self.obj_pos_x.value()
        obj['center'][1] = self.obj_pos_y.value()
        obj['center'][2] = self.obj_pos_z.value()
        obj['radius'] = self.obj_radius.value()
        self.update_obj_list()

    def choose_obj_color(self):
        if self.selected_obj_index is None:
            return
        obj = self.objects[self.selected_obj_index]
        initial = QColor(
            int(obj['color'][0]*255),
            int(obj['color'][1]*255),
            int(obj['color'][2]*255)
        )
        color = QColorDialog.getColor(initial, self, "Küre Rengi Seç")
        if color.isValid():
            obj['color'] = np.array([color.red()/255, color.green()/255, color.blue()/255])
            self.update_obj_list()

    def on_light_selected(self, index):
        if index < 0 or index >= len(self.lights):
            self.selected_light_index = None
            return
        self.selected_light_index = index
        light = self.lights[index]

        self.light_pos_x.blockSignals(True)
        self.light_pos_y.blockSignals(True)
        self.light_pos_z.blockSignals(True)
        self.light_radius.blockSignals(True)
        self.light_power.blockSignals(True)
        self.light_speed.blockSignals(True)
        self.light_phase.blockSignals(True)

        self.light_pos_x.setValue(light['pos'][0])
        self.light_pos_y.setValue(light['pos'][1])
        self.light_pos_z.setValue(light['pos'][2])
        self.light_radius.setValue(light['radius'])
        self.light_power.setValue(light.get('power', 1.0))
        self.light_speed.setValue(light.get('speed', 0.0))
        self.light_phase.setValue(light.get('phase', 0.0))

        self.light_pos_x.blockSignals(False)
        self.light_pos_y.blockSignals(False)
        self.light_pos_z.blockSignals(False)
        self.light_radius.blockSignals(False)
        self.light_power.blockSignals(False)
        self.light_speed.blockSignals(False)
        self.light_phase.blockSignals(False)

    def update_selected_light(self):
        if self.selected_light_index is None:
            return
        light = self.lights[self.selected_light_index]
        light['pos'][0] = self.light_pos_x.value()
        light['pos'][1] = self.light_pos_y.value()
        light['pos'][2] = self.light_pos_z.value()
        light['radius'] = self.light_radius.value()
        light['power'] = self.light_power.value()
        light['speed'] = self.light_speed.value()
        light['phase'] = self.light_phase.value()
        self.update_light_list()

    def choose_light_color(self):
        if self.selected_light_index is None:
            return
        light = self.lights[self.selected_light_index]
        initial = QColor(
            int(light['color'][0]*255),
            int(light['color'][1]*255),
            int(light['color'][2]*255)
        )
        color = QColorDialog.getColor(initial, self, "Işık Rengi Seç")
        if color.isValid():
            light['color'] = np.array([color.red()/255, color.green()/255, color.blue()/255])
            self.update_light_list()

    def add_light(self):
        new_light = {
            'pos': np.array([2.0, 2.0, 1.0]),
            'color': np.array([1.0, 1.0, 0.5]),
            'radius': 0.1,
            'power': 1.0,
            'speed': 0.0,
            'phase': 0.0
        }
        self.lights.append(new_light)
        self.update_light_list()

    def start_render_thread(self):
        self.render_thread = RenderThread(
            self.RENDER_WIDTH, self.RENDER_HEIGHT,
            self.objects, self.lights,
            self.camera_pos, self.camera_dir, self.background_color
        )
        self.render_thread.rendered.connect(self.on_rendered)
        self.render_thread.start()

    def start_fps_timer(self):
        self.frame_count = 0
        self.last_time = time.time()
        self.fps = 0
        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self.calculate_fps)
        self.fps_timer.start(1000)

    def calculate_fps(self):
        self.fps = self.frame_count
        self.frame_count = 0
        self.setWindowTitle(f"Ray Tracer GUI - FPS: {self.fps}")
    
    def on_rendered(self, img_array):
        self.frame_count += 1
        h, w, _ = img_array.shape
        bytes_per_line = 3 * w
        qimg = QImage(img_array.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)

        pix = pix.scaled(self.WIDTH, self.HEIGHT, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(pix)

    def closeEvent(self, event):
        if hasattr(self, 'render_thread'):
            self.render_thread.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RayTracerGUI()
    window.show()
    sys.exit(app.exec_())
