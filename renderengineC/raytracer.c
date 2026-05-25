#include <math.h>
#include <stdlib.h>

// Vektör yapısı ve temel matematik fonksiyonları
typedef struct { float x, y, z; } vec3;

vec3 v_sub(vec3 a, vec3 b) { return (vec3){a.x - b.x, a.y - b.y, a.z - b.z}; }
vec3 v_add(vec3 a, vec3 b) { return (vec3){a.x + b.x, a.y + b.y, a.z + b.z}; }
vec3 v_mul(vec3 a, vec3 b) { return (vec3){a.x * b.x, a.y * b.y, a.z * b.z}; }
vec3 v_scale(vec3 v, float s) { return (vec3){v.x * s, v.y * s, v.z * s}; }
float v_dot(vec3 a, vec3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
float v_mag(vec3 v) { return sqrtf(v_dot(v, v)); }
vec3 v_norm(vec3 v) {
    float mag = v_mag(v);
    if (mag < 1e-8f) return (vec3){0, 0, 0};
    return v_scale(v, 1.0f / mag);
}

// Işın ve Geometrik Objeler
typedef struct { vec3 origin; vec3 dir; } Ray;
typedef struct { vec3 center; float radius; vec3 color; } Sphere;
typedef struct { vec3 point; vec3 normal; vec3 color; } Plane;
typedef struct { vec3 pos; vec3 color; } Light;

// Küre ile kesişim (Diskriminant formülü)
float hit_sphere(Ray ray, Sphere s) {
    vec3 oc = v_sub(ray.origin, s.center);
    float a = v_dot(ray.dir, ray.dir);
    float b = 2.0f * v_dot(oc, ray.dir);
    float c = v_dot(oc, oc) - s.radius * s.radius;
    float discriminant = b * b - 4 * a * c;
    
    if (discriminant < 0) return -1.0f;
    
    float t = (-b - sqrtf(discriminant)) / (2.0f * a);
    if (t > 0.001f) return t;
    t = (-b + sqrtf(discriminant)) / (2.0f * a);
    if (t > 0.001f) return t;
    return -1.0f;
}

// Düzlem ile kesişim
float hit_plane(Ray ray, Plane p) {
    float denom = v_dot(ray.dir, p.normal);
    if (fabsf(denom) < 1e-6f) return -1.0f;
    float t = v_dot(v_sub(p.point, ray.origin), p.normal) / denom;
    return t > 0.001f ? t : -1.0f;
}

// Python'dan çağrılacak Ana Render Fonksiyonu
void render_c(unsigned char* pixels, int width, int height,
              vec3 camera_pos, vec3 bg_color,
              Sphere* spheres, int num_spheres,
              Plane* planes, int num_planes,
              Light* lights, int num_lights) {
                  
    float aspect_ratio = (float)width / height;

    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            // Ekran koordinatlarını (-1 to 1) uzayına çevirme
            float u = (2.0f * (x + 0.5f) / width - 1.0f) * aspect_ratio;
            float v = 1.0f - 2.0f * (y + 0.5f) / height;

            Ray ray;
            ray.origin = camera_pos;
            ray.dir = v_norm((vec3){u, v, 1.0f});

            float closest_t = 1e30f;
            vec3 pixel_color = bg_color;
            vec3 hit_normal, hit_point, obj_color;
            int hit_anything = 0;

            // Küreleri Kontrol Et
            for (int i = 0; i < num_spheres; i++) {
                float t = hit_sphere(ray, spheres[i]);
                if (t > 0 && t < closest_t) {
                    closest_t = t;
                    hit_anything = 1;
                    hit_point = v_add(ray.origin, v_scale(ray.dir, t));
                    hit_normal = v_norm(v_sub(hit_point, spheres[i].center));
                    obj_color = spheres[i].color;
                }
            }

            // Düzlemleri Kontrol Et
            for (int i = 0; i < num_planes; i++) {
                float t = hit_plane(ray, planes[i]);
                if (t > 0 && t < closest_t) {
                    closest_t = t;
                    hit_anything = 1;
                    hit_point = v_add(ray.origin, v_scale(ray.dir, t));
                    hit_normal = v_norm(planes[i].normal);
                    obj_color = planes[i].color;
                }
            }

            // Çarpışma varsa Işıklandırmayı (Diffuse + Ambient) hesapla
            if (hit_anything) {
                vec3 final_color = v_scale(obj_color, 0.1f); // Ambient ışık (0.1 şiddetinde)
                
                for (int i = 0; i < num_lights; i++) {
                    vec3 to_light = v_norm(v_sub(lights[i].pos, hit_point));
                    float diff = fmaxf(0.0f, v_dot(hit_normal, to_light)); // Nokta çarpımı
                    vec3 diffuse = v_scale(v_mul(obj_color, lights[i].color), diff);
                    final_color = v_add(final_color, diffuse);
                }
                pixel_color = final_color;
            }

            // Renkleri 0-255 aralığına oturt ve NumPy dizisine (RAM'e) yaz
            int index = (y * width + x) * 3;
            pixels[index] = (unsigned char)fminf(255.0f, fmaxf(0.0f, pixel_color.x * 255.0f));
            pixels[index+1] = (unsigned char)fminf(255.0f, fmaxf(0.0f, pixel_color.y * 255.0f));
            pixels[index+2] = (unsigned char)fminf(255.0f, fmaxf(0.0f, pixel_color.z * 255.0f));
        }
    }
}
