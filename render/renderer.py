import ctypes
import numpy as np
import os

class Vec3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float)]

class Sphere(ctypes.Structure):
    _fields_ = [("center", Vec3), ("radius", ctypes.c_float), ("color", Vec3), ("reflectivity", ctypes.c_float)]

class Plane(ctypes.Structure):
    _fields_ = [("point", Vec3), ("normal", Vec3), ("color", Vec3), ("reflectivity", ctypes.c_float)]

# Işık Gücü (power) eklendi
class Light(ctypes.Structure):
    _fields_ = [("pos", Vec3), ("color", Vec3), ("power", ctypes.c_float)]

lib_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'libengine.so')
engine = ctypes.CDLL(lib_path)

# 3 adet Vec3 yan yana: camera_pos, camera_dir, background_color
engine.render_c.argtypes = [
    np.ctypeslib.ndpointer(dtype=np.uint8, ndim=3, flags='C_CONTIGUOUS'),
    ctypes.c_int, ctypes.c_int,
    Vec3, Vec3, Vec3,
    ctypes.POINTER(Sphere), ctypes.c_int,
    ctypes.POINTER(Plane), ctypes.c_int,
    ctypes.POINTER(Light), ctypes.c_int
]

def render(width, height, objects, lights, camera_pos, camera_dir, background_color, samples_per_pixel=1):
    pixel_colors = np.zeros((height, width, 3), dtype=np.uint8)

    # Parametreler doğru sırayla alınıyor
    cam_c = Vec3(camera_pos[0], camera_pos[1], camera_pos[2])
    dir_c = Vec3(camera_dir[0], camera_dir[1], camera_dir[2])
    bg_c = Vec3(background_color[0], background_color[1], background_color[2])

    py_spheres = []
    py_planes = []
    for obj in objects:
        c_color = Vec3(obj['color'][0], obj['color'][1], obj['color'][2])
        refl = float(obj.get('reflectivity', 0.0)) 
        
        if obj['type'] == 'sphere':
            c_center = Vec3(obj['center'][0], obj['center'][1], obj['center'][2])
            py_spheres.append(Sphere(c_center, obj['radius'], c_color, refl))
        elif obj['type'] == 'plane':
            norm = obj['normal'] / np.linalg.norm(obj['normal'])
            c_normal = Vec3(norm[0], norm[1], norm[2])
            c_point = Vec3(obj['point'][0], obj['point'][1], obj['point'][2])
            py_planes.append(Plane(c_point, c_normal, c_color, refl))

    py_lights = []
    for l in lights:
        c_pos = Vec3(l['pos'][0], l['pos'][1], l['pos'][2])
        c_lcolor = Vec3(l['color'][0], l['color'][1], l['color'][2])
        c_power = ctypes.c_float(l.get('power', 1.0)) # Arayüzden gelen güç okunuyor
        py_lights.append(Light(c_pos, c_lcolor, c_power))

    SphereArray = Sphere * len(py_spheres)
    PlaneArray = Plane * len(py_planes)
    LightArray = Light * len(py_lights)

    # C fonksiyonuna tam olarak eşleşen sırayla gönderiliyor
    engine.render_c(
        pixel_colors, width, height,
        cam_c, dir_c, bg_c,
        SphereArray(*py_spheres) if py_spheres else None, len(py_spheres),
        PlaneArray(*py_planes) if py_planes else None, len(py_planes),
        LightArray(*py_lights) if py_lights else None, len(py_lights)
    )

    return pixel_colors
