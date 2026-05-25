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

    def __init__(self, width, height, objects, lights, camera_pos, background_color, parent=None):
        super().__init__(parent)
        self.width = width
        self.height = height
        self.objects = objects
        self.lights = lights
        self.camera_pos = camera_pos
        self.background_color = background_color
        self.frame = 0
        self.running = True

    def run(self):
        while self.running:
            self.frame += 1
            for light in self.lights:
                if light['speed'] != 0:
                    angle = self.frame * 0.05 * light['speed'] + light['phase']
                    radius = np.linalg.norm(light['pos'][[0, 2]])
                    light['pos'][0] = radius * np.cos(angle)
                    light['pos'][2] = radius * np.sin(angle)

            img_array = renderer.render(
                self.width, self.height,
                self.objects, self.lights,
                self.camera_pos, self.background_color
            )

            self.rendered.emit(img_array)
            self.msleep(0)

    def stop(self):
        self.running = False
        self.wait()

class RayTracerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ray Tracer GUI")
        self.WIDTH = 1280
        self.HEIGHT = 720
        k = 1
        self.RENDER_WIDTH = self.WIDTH // k
        self.RENDER_HEIGHT = self.HEIGHT // k
        self.camera_pos = np.array([0.0, 0.0, -3.0])
        self.background_color = np.array([0.05, 0.05, 0.05])

        self.objects = []
        self.lights = []
        self.selected_obj_index = None
        self.selected_light_index = None

        self.init_ui()
        self.start_render_thread()
        self.start_fps_timer()
        self.setFocusPolicy(Qt.StrongFocus)
        
        
        # --- KLAVYE KONTROLLERİ ---
    def keyPressEvent(self, event):
        hiz = 0.5  # Kameranın adım büyüklüğü
        
        # W ve S: İleri / Geri (Z ekseni)
        if event.key() == Qt.Key_W:
            self.camera_pos[2] += hiz
        elif event.key() == Qt.Key_S:
            self.camera_pos[2] -= hiz
            
        # A ve D: Sağa / Sola (X ekseni)
        elif event.key() == Qt.Key_A:
            self.camera_pos[0] -= hiz
        elif event.key() == Qt.Key_D:
            self.camera_pos[0] += hiz
            
        # Boşluk ve Shift: Yukarı / Aşağı (Y ekseni)
        elif event.key() == Qt.Key_Space:
            self.camera_pos[1] += hiz
        elif event.key() == Qt.Key_Shift:
            self.camera_pos[1] -= hiz

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        self.image_label = QLabel()
        self.image_label.setFixedSize(self.WIDTH, self.HEIGHT)
        main_layout.addWidget(self.image_label)

        control_panel = QVBoxLayout()
        main_layout.addLayout(control_panel)

        control_panel.addWidget(QLabel("Küreler:"))
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

        self.obj_params_layout.addRow("Pozisyon X:", self.obj_pos_x)
        self.obj_params_layout.addRow("Pozisyon Y:", self.obj_pos_y)
        self.obj_params_layout.addRow("Pozisyon Z:", self.obj_pos_z)
        self.obj_params_layout.addRow("Yarıçap:", self.obj_radius)
        self.obj_params_layout.addRow("Renk:", self.obj_color_btn)

        self.obj_add_btn = QPushButton("Küre Ekle")
        self.obj_add_btn.clicked.connect(self.add_object)
        control_panel.addWidget(self.obj_add_btn)

        self.plane_add_btn = QPushButton("Düzlem Ekle")
        self.plane_add_btn.clicked.connect(self.add_plane)
        control_panel.addWidget(self.plane_add_btn)

        control_panel.addSpacing(20)

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
        self.light_speed = QDoubleSpinBox(); self.light_speed.setRange(0, 10); self.light_speed.setSingleStep(0.1)
        self.light_phase = QDoubleSpinBox(); self.light_phase.setRange(0, 2*math.pi); self.light_phase.setSingleStep(0.1)

        self.light_pos_x.valueChanged.connect(self.update_selected_light)
        self.light_pos_y.valueChanged.connect(self.update_selected_light)
        self.light_pos_z.valueChanged.connect(self.update_selected_light)
        self.light_radius.valueChanged.connect(self.update_selected_light)
        self.light_speed.valueChanged.connect(self.update_selected_light)
        self.light_phase.valueChanged.connect(self.update_selected_light)

        self.light_color_btn = QPushButton("Renk Seç")
        self.light_color_btn.clicked.connect(self.choose_light_color)

        self.light_params_layout.addRow("Pozisyon X:", self.light_pos_x)
        self.light_params_layout.addRow("Pozisyon Y:", self.light_pos_y)
        self.light_params_layout.addRow("Pozisyon Z:", self.light_pos_z)
        self.light_params_layout.addRow("Yarıçap:", self.light_radius)
        self.light_params_layout.addRow("Renk:", self.light_color_btn)
        self.light_params_layout.addRow("Dönme Hızı:", self.light_speed)
        self.light_params_layout.addRow("Faz (rad):", self.light_phase)

        self.light_add_btn = QPushButton("Işık Ekle")
        self.light_add_btn.clicked.connect(self.add_light)
        control_panel.addWidget(self.light_add_btn)

        self.update_obj_list()
        self.update_light_list()

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

    def add_object(self):
        new_obj = {
            'type': 'sphere',
            'center': np.array([0.0, 0.0, 1.0]),
            'radius': 0.5,
            'color': np.array([1.0, 1.0, 1.0]),
            'reflectivity': 0.8  # 0.0 mat, 1.0 tam ayna
            }
        self.objects.append(new_obj)
        self.update_obj_list()

    def add_plane(self):
        new_obj = {
            'type': 'plane',
            'point': np.array([0.0, -0.5, 0.0]),
            'normal': np.array([0.0, 1.0, 0.0]),
            'color': np.array([0.5, 0.5, 0.5]),
            'reflectivity': 0.8  # 0.0 mat, 1.0 tam ayna
        }
        self.objects.append(new_obj)
        self.update_obj_list()
    def update_light_list(self):
        self.light_list.clear()
        for i, light in enumerate(self.lights):
            self.light_list.addItem(f"Işık {i}: Pos({light['pos'][0]:.2f},{light['pos'][1]:.2f},{light['pos'][2]:.2f}) R:{light['radius']:.2f}")

    # Küre seçimi
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
        self.obj_radius.setValue(obj['radius'])

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

    # Işık seçimi
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
        self.light_speed.blockSignals(True)
        self.light_phase.blockSignals(True)

        self.light_pos_x.setValue(light['pos'][0])
        self.light_pos_y.setValue(light['pos'][1])
        self.light_pos_z.setValue(light['pos'][2])
        self.light_radius.setValue(light['radius'])
        self.light_speed.setValue(light.get('speed', 0.0))
        self.light_phase.setValue(light.get('phase', 0.0))

        self.light_pos_x.blockSignals(False)
        self.light_pos_y.blockSignals(False)
        self.light_pos_z.blockSignals(False)
        self.light_radius.blockSignals(False)
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

    def add_object(self):
        new_obj = {
            'center': np.array([0.0, 0.0, 1.0]),
            'radius': 0.5,
            'color': np.array([1.0, 1.0, 1.0])
        }
        self.objects.append(new_obj)
        self.update_obj_list()

    def add_light(self):
        new_light = {
            'pos': np.array([2.0, 2.0, 1.0]),
            'color': np.array([1.0, 1.0, 0.5]),
            'radius': 0.1,
            'speed': 0.0,
            'phase': 0.0
        }
        self.lights.append(new_light)
        self.update_light_list()

    def start_render_thread(self):
        self.render_thread = RenderThread(
            self.RENDER_WIDTH, self.RENDER_HEIGHT,
            self.objects, self.lights,
            self.camera_pos, self.background_color
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
    
    # Bu method render thread'den gelen sinyal ile çağrılır
    def on_rendered(self, img_array):
        print("Render çıktı shape:", img_array.shape, "dtype:", img_array.dtype)
        self.frame_count += 1
        h, w, _ = img_array.shape
        bytes_per_line = 3 * w
        qimg = QImage(img_array.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)

        # Burada upscale yapıyoruz
        pix = pix.scaled(self.WIDTH, self.HEIGHT, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(pix)

    def closeEvent(self, event):
        # Kapanırken render thread düzgün kapansın
        if hasattr(self, 'render_thread'):
            self.render_thread.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RayTracerGUI()
    window.show()
    sys.exit(app.exec_())


