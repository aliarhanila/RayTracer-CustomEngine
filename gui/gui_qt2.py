import sys
import numpy as np
import math
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QColorDialog, QFormLayout, QDoubleSpinBox, 
    QMessageBox, QComboBox, QGroupBox
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
        self.setWindowTitle("Ray Tracer Custom Engine - Viewport")
        
        self.WIDTH = 1280
        self.HEIGHT = 720
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
        
        # Hiyerarşi takibi için yeni değişkenler
        self.selected_type = None  # 'object' veya 'light'
        self.selected_index = None
        self.hierarchy_mapping = [] # Liste satırlarını verilere bağlar

        self.init_ui()
        self.start_render_thread()
        self.start_fps_timer()
        
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.game_timer = QTimer()
        self.game_timer.timeout.connect(self.update_movement)
        self.game_timer.start(16)

    # --- INPUT AND MOVEMENT ---
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

    # --- UI INITIALIZATION (ENGLISH) ---
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Viewport Screen
        self.image_label = QLabel()
        self.image_label.setFixedSize(self.WIDTH, self.HEIGHT)
        main_layout.addWidget(self.image_label)

        # Control Panel (Right Side)
        control_panel = QVBoxLayout()
        main_layout.addLayout(control_panel)

        # 1. Scene Hierarchy Group
        hierarchy_group = QGroupBox("Scene Hierarchy")
        hierarchy_layout = QVBoxLayout()
        self.hierarchy_list = QListWidget()
        self.hierarchy_list.currentRowChanged.connect(self.on_hierarchy_selected)
        hierarchy_layout.addWidget(self.hierarchy_list)
        
        # Add Buttons inside Hierarchy
        add_buttons_layout = QHBoxLayout()
        self.add_sphere_btn = QPushButton("+ Sphere")
        self.add_sphere_btn.clicked.connect(self.add_sphere)
        self.add_plane_btn = QPushButton("+ Plane")
        self.add_plane_btn.clicked.connect(self.add_plane)
        self.add_light_btn = QPushButton("+ Light")
        self.add_light_btn.clicked.connect(self.add_light)
        
        add_buttons_layout.addWidget(self.add_sphere_btn)
        add_buttons_layout.addWidget(self.add_plane_btn)
        add_buttons_layout.addWidget(self.add_light_btn)
        hierarchy_layout.addLayout(add_buttons_layout)
        hierarchy_group.setLayout(hierarchy_layout)
        control_panel.addWidget(hierarchy_group)

        # 2. Inspector / Properties Group
        properties_group = QGroupBox("Details / Inspector")
        self.params_layout = QFormLayout()

        self.pos_x = QDoubleSpinBox(); self.pos_x.setRange(-10, 10); self.pos_x.setSingleStep(0.1)
        self.pos_y = QDoubleSpinBox(); self.pos_y.setRange(-10, 10); self.pos_y.setSingleStep(0.1)
        self.pos_z = QDoubleSpinBox(); self.pos_z.setRange(-10, 10); self.pos_z.setSingleStep(0.1)
        self.radius_spin = QDoubleSpinBox(); self.radius_spin.setRange(0.01, 5); self.radius_spin.setSingleStep(0.01)
        self.power_spin = QDoubleSpinBox(); self.power_spin.setRange(0.0, 50.0); self.power_spin.setSingleStep(0.5)
        self.speed_spin = QDoubleSpinBox(); self.speed_spin.setRange(0, 10); self.speed_spin.setSingleStep(0.1)
        self.phase_spin = QDoubleSpinBox(); self.phase_spin.setRange(0, 2*math.pi); self.phase_spin.setSingleStep(0.1)

        self.pos_x.valueChanged.connect(self.update_selected_element)
        self.pos_y.valueChanged.connect(self.update_selected_element)
        self.pos_z.valueChanged.connect(self.update_selected_element)
        self.radius_spin.valueChanged.connect(self.update_selected_element)
        self.power_spin.valueChanged.connect(self.update_selected_element)
        self.speed_spin.valueChanged.connect(self.update_selected_element)
        self.phase_spin.valueChanged.connect(self.update_selected_element)

        self.color_btn = QPushButton("Select Color")
        self.color_btn.clicked.connect(self.choose_element_color)

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setStyleSheet("background-color: #ff4c4c; color: white; font-weight: bold;")
        self.delete_btn.clicked.connect(self.delete_selected)

        self.params_layout.addRow("Position X:", self.pos_x)
        self.params_layout.addRow("Position Y:", self.pos_y)
        self.params_layout.addRow("Position Z:", self.pos_z)
        self.params_layout.addRow("Radius:", self.radius_spin)
        self.params_layout.addRow("Light Power:", self.power_spin)
        self.params_layout.addRow("Rotation Speed:", self.speed_spin)
        self.params_layout.addRow("Phase (rad):", self.phase_spin)
        self.params_layout.addRow("Material Color:", self.color_btn)
        self.params_layout.addRow("", self.delete_btn)
        properties_group.setLayout(self.params_layout)
        control_panel.addWidget(properties_group)

        # 3. Engine Settings Group (New Screen Modes)
        settings_group = QGroupBox("System Settings")
        settings_layout = QFormLayout()
        self.screen_mode_combo = QComboBox()
        self.screen_mode_combo.addItems(["Windowed (1280x720)", "Fullscreen Mode"])
        self.screen_mode_combo.currentIndexChanged.connect(self.change_screen_mode)
        settings_layout.addRow("Display Mode:", self.screen_mode_combo)
        settings_group.setLayout(settings_layout)
        control_panel.addWidget(settings_group)

        self.rebuild_hierarchy_list()

    # --- HIERARCHY SYSTEM LOGIC ---
    def rebuild_hierarchy_list(self):
        self.hierarchy_list.blockSignals(True)
        self.hierarchy_list.clear()
        self.hierarchy_mapping = []

        # List Objects (Spheres & Planes)
        for i, obj in enumerate(self.objects):
            if 'type' not in obj: obj['type'] = 'sphere'
            
            if obj['type'] == 'sphere':
                label = f"Sphere (ID: {i}) - Pos:({obj['center'][0]:.1f}, {obj['center'][1]:.1f}, {obj['center'][2]:.1f})"
            else:
                label = f"Plane (ID: {i}) - Point:({obj['point'][0]:.1f}, {obj['point'][1]:.1f}, {obj['point'][2]:.1f})"
            
            self.hierarchy_list.addItem(label)
            self.hierarchy_mapping.append(('object', i))

        # List Lights
        for i, light in enumerate(self.lights):
            label = f"Light (ID: {i}) - Power: {light.get('power', 1.0):.1f}"
            self.hierarchy_list.addItem(label)
            self.hierarchy_mapping.append(('light', i))

        self.hierarchy_list.blockSignals(False)

    def on_hierarchy_selected(self, index):
        if index < 0 or index >= len(self.hierarchy_mapping):
            self.selected_type = None
            self.selected_index = None
            return
            
        self.selected_type, self.selected_index = self.hierarchy_mapping[index]
        
        # Block inputs to prevent write-back feedback loops
        self.block_all_signals(True)

        if self.selected_type == 'object':
            obj = self.objects[self.selected_index]
            # BUG FIX HERE: Check if type is plane or sphere
            if obj['type'] == 'sphere':
                self.pos_x.setValue(obj['center'][0])
                self.pos_y.setValue(obj['center'][1])
                self.pos_z.setValue(obj['center'][2])
                self.radius_spin.setValue(obj['radius'])
                self.radius_spin.setEnabled(True)
            else: # Plane
                self.pos_x.setValue(obj['point'][0])
                self.pos_y.setValue(obj['point'][1])
                self.pos_z.setValue(obj['point'][2])
                self.radius_spin.setValue(0.0)
                self.radius_spin.setEnabled(False) # Planes don't have a radius

            # Disable light parameters
            self.power_spin.setEnabled(False)
            self.speed_spin.setEnabled(False)
            self.phase_spin.setEnabled(False)

        elif self.selected_type == 'light':
            light = self.lights[self.selected_index]
            self.pos_x.setValue(light['pos'][0])
            self.pos_y.setValue(light['pos'][1])
            self.pos_z.setValue(light['pos'][2])
            self.radius_spin.setValue(light['radius'])
            self.radius_spin.setEnabled(True)
            
            self.power_spin.setValue(light.get('power', 1.0))
            self.speed_spin.setValue(light.get('speed', 0.0))
            self.phase_spin.setValue(light.get('phase', 0.0))
            
            self.power_spin.setEnabled(True)
            self.speed_spin.setEnabled(True)
            self.phase_spin.setEnabled(True)

        self.block_all_signals(False)

    def update_selected_element(self):
        if self.selected_index is None or self.selected_type is None:
            return

        if self.selected_type == 'object':
            obj = self.objects[self.selected_index]
            if obj['type'] == 'sphere':
                obj['center'][0] = self.pos_x.value()
                obj['center'][1] = self.pos_y.value()
                obj['center'][2] = self.pos_z.value()
                obj['radius'] = self.radius_spin.value()
            else: # Plane
                obj['point'][0] = self.pos_x.value()
                obj['point'][1] = self.pos_y.value()
                obj['point'][2] = self.pos_z.value()
                
        elif self.selected_type == 'light':
            light = self.lights[self.selected_index]
            light['pos'][0] = self.pos_x.value()
            light['pos'][1] = self.pos_y.value()
            light['pos'][2] = self.pos_z.value()
            light['radius'] = self.radius_spin.value()
            light['power'] = self.power_spin.value()
            light['speed'] = self.speed_spin.value()
            light['phase'] = self.phase_spin.value()

        # Pürüzsüz güncelleme için listeyi tamamen bozmadan sadece seçili satırın metnini tazele
        self.hierarchy_list.blockSignals(True)
        curr_row = self.hierarchy_list.currentRow()
        if self.selected_type == 'object':
            obj = self.objects[self.selected_index]
            if obj['type'] == 'sphere':
                self.hierarchy_list.item(curr_row).setText(f"Sphere (ID: {self.selected_index}) - Pos:({obj['center'][0]:.1f}, {obj['center'][1]:.1f}, {obj['center'][2]:.1f})")
            else:
                self.hierarchy_list.item(curr_row).setText(f"Plane (ID: {self.selected_index}) - Point:({obj['point'][0]:.1f}, {obj['point'][1]:.1f}, {obj['point'][2]:.1f})")
        elif self.selected_type == 'light':
            light = self.lights[self.selected_index]
            self.hierarchy_list.item(curr_row).setText(f"Light (ID: {self.selected_index}) - Power: {light['power']:.1f}")
        self.hierarchy_list.blockSignals(False)

    def choose_element_color(self):
        if self.selected_index is None or self.selected_type is None:
            return
            
        elem = self.objects[self.selected_index] if self.selected_type == 'object' else self.lights[self.selected_index]
        initial = QColor(int(elem['color'][0]*255), int(elem['color'][1]*255), int(elem['color'][2]*255))
        
        color = QColorDialog.getColor(initial, self, "Select Color")
        if color.isValid():
            elem['color'] = np.array([color.red()/255, color.green()/255, color.blue()/255])

    def delete_selected(self):
        if self.selected_index is None or self.selected_type is None:
            return
            
        if self.selected_type == 'object':
            self.objects.pop(self.selected_index)
        elif self.selected_type == 'light':
            self.lights.pop(self.selected_index)
            
        self.selected_index = None
        self.selected_type = None
        self.rebuild_hierarchy_list()
        self.setFocus()

    # --- ADD ELEMENT TRIGGERS ---
    def add_sphere(self):
        self.objects.append({
            'type': 'sphere', 'center': np.array([0.0, 0.0, 1.0]),
            'radius': 0.5, 'color': np.array([1.0, 1.0, 1.0]), 'reflectivity': 0.8
        })
        self.rebuild_hierarchy_list()

    def add_plane(self):
        self.objects.append({
            'type': 'plane', 'point': np.array([0.0, -0.5, 0.0]),
            'normal': np.array([0.0, 1.0, 0.0]), 'color': np.array([0.5, 0.5, 0.5]), 'reflectivity': 0.5
        })
        self.rebuild_hierarchy_list()

    def add_light(self):
        self.lights.append({
            'pos': np.array([2.0, 2.0, 1.0]), 'color': np.array([1.0, 1.0, 0.5]),
            'radius': 0.1, 'power': 5.0, 'speed': 0.0, 'phase': 0.0
        })
        self.rebuild_hierarchy_list()

    # --- DISPLAY MODE MANAGEMENT ---
    def change_screen_mode(self, index):
        if index == 0:
            self.showNormal()
        elif index == 1:
            self.showFullScreen()
        self.setFocus()

    def block_all_signals(self, block=True):
        self.pos_x.blockSignals(block)
        self.pos_y.blockSignals(block)
        self.pos_z.blockSignals(block)
        self.radius_spin.blockSignals(block)
        self.power_spin.blockSignals(block)
        self.speed_spin.blockSignals(block)
        self.phase_spin.blockSignals(block)

    # --- ENGINE TIMERS ---
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
        self.setWindowTitle(f"Ray Tracer Engine Viewport - FPS: {self.fps}")
    
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
