#include <math.h>
#include <stdlib.h>

// --- Vektör Matematiği ---
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

// Yansıma Vektörü Formülü: R = I - 2(I.N)N
vec3 reflect(vec3 i, vec3 n) {
    return v_sub(i, v_scale(n, 2.0f * v_dot(i, n)));
}

// --- Geometrik Yapılar ---
typedef struct { vec3 origin; vec3 dir; } Ray;
typedef struct { vec3 center; float radius; vec3 color; float reflectivity; } Sphere;
typedef struct { vec3 point; vec3 normal; vec3 color; float reflectivity; } Plane;
typedef struct { vec3 pos; vec3 color; } Light;

#define MAX_BOUNCES 3  // Işın maksimum kaç kere sekecek?

// Küre ile kesişim
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

// --- Recursive (Özyinelemeli) Ray Tracing Fonksiyonu ---
vec3 trace_ray(Ray ray, Sphere* spheres, int num_spheres, Plane* planes, int num_planes, Light* lights, int num_lights, vec3 bg_color, int depth) {
    if (depth > MAX_BOUNCES) return bg_color; // Sınırı aşarsa arkaplanı döndür

    float closest_t = 1e30f;
    vec3 hit_normal, hit_point, obj_color;
    float obj_reflectivity = 0.0f;
    int hit_anything = 0;

    // Küreleri Kontrol Et
    for (int i = 0; i < num_spheres; i++) {
        float t = hit_sphere(ray, spheres[i]);
        if (t > 0 && t < closest_t) {
            closest_t = t; hit_anything = 1;
            hit_point = v_add(ray.origin, v_scale(ray.dir, t));
            hit_normal = v_norm(v_sub(hit_point, spheres[i].center));
            obj_color = spheres[i].color;
            obj_reflectivity = spheres[i].reflectivity;
        }
    }

    // Düzlemleri Kontrol Et
    for (int i = 0; i < num_planes; i++) {
        float t = hit_plane(ray, planes[i]);
        if (t > 0 && t < closest_t) {
            closest_t = t; hit_anything = 1;
            hit_point = v_add(ray.origin, v_scale(ray.dir, t));
            hit_normal = v_norm(planes[i].normal);
            obj_color = planes[i].color;
            obj_reflectivity = planes[i].reflectivity;
        }
    }

    if (!hit_anything) return bg_color;

    // --- Işıklandırma ve Gölgeler (Shadow Rays) ---
    vec3 local_color = v_scale(obj_color, 0.1f); // Ambient ışık
    
    for (int i = 0; i < num_lights; i++) {
        vec3 to_light = v_sub(lights[i].pos, hit_point);
        float dist_to_light = v_mag(to_light);
        to_light = v_scale(to_light, 1.0f / dist_to_light);

        // Kendi kendine çarpmaması için yüzeyden çok hafif (0.001f) ileri itiyoruz
        Ray shadow_ray = {v_add(hit_point, v_scale(hit_normal, 0.001f)), to_light};
        int in_shadow = 0;

        // Gölge için nesneleri tekrar kontrol et
        for (int j = 0; j < num_spheres; j++) {
            float t = hit_sphere(shadow_ray, spheres[j]);
            if (t > 0 && t < dist_to_light) { in_shadow = 1; break; }
        }
        for (int j = 0; j < num_planes && !in_shadow; j++) {
            float t = hit_plane(shadow_ray, planes[j]);
            if (t > 0 && t < dist_to_light) { in_shadow = 1; break; }
        }

        // Eğer arada nesne yoksa aydınlat (Diffuse)
        if (!in_shadow) {
            float diff = fmaxf(0.0f, v_dot(hit_normal, to_light));
            vec3 diffuse = v_scale(v_mul(obj_color, lights[i].color), diff);
            local_color = v_add(local_color, diffuse);
        }
    }

    // --- Yansıma (Reflection) ---
    if (obj_reflectivity > 0.0f) {
        Ray ref_ray;
        ref_ray.origin = v_add(hit_point, v_scale(hit_normal, 0.001f)); // Kendi yüzeyine çarpmasın diye itme
        ref_ray.dir = reflect(ray.dir, hit_normal);
        
        // Işını tekrar sahneye fırlat
        vec3 ref_color = trace_ray(ref_ray, spheres, num_spheres, planes, num_planes, lights, num_lights, bg_color, depth + 1);

        // Kendi rengi ile yansıyan rengi karıştır
        vec3 final_color;
        final_color.x = local_color.x * (1.0f - obj_reflectivity) + ref_color.x * obj_reflectivity;
        final_color.y = local_color.y * (1.0f - obj_reflectivity) + ref_color.y * obj_reflectivity;
        final_color.z = local_color.z * (1.0f - obj_reflectivity) + ref_color.z * obj_reflectivity;
        return final_color;
    }

    return local_color;
}

// --- Ana Render Fonksiyonu ---
void render_c(unsigned char* pixels, int width, int height,
              vec3 camera_pos, vec3 bg_color,
              Sphere* spheres, int num_spheres,
              Plane* planes, int num_planes,
              Light* lights, int num_lights) {
                  
    float aspect_ratio = (float)width / height;

    #pragma omp parallel for // Eğer sistemin destekliyorsa işlemci çekirdeklerini böler (hızlandırır)
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            float u = (2.0f * (x + 0.5f) / width - 1.0f) * aspect_ratio;
            float v = 1.0f - 2.0f * (y + 0.5f) / height;

            Ray ray = {camera_pos, v_norm((vec3){u, v, 1.0f})};
            
            // Işını fırlat!
            vec3 pixel_color = trace_ray(ray, spheres, num_spheres, planes, num_planes, lights, num_lights, bg_color, 0);

            int index = (y * width + x) * 3;
            pixels[index] = (unsigned char)fminf(255.0f, fmaxf(0.0f, pixel_color.x * 255.0f));
            pixels[index+1] = (unsigned char)fminf(255.0f, fmaxf(0.0f, pixel_color.y * 255.0f));
            pixels[index+2] = (unsigned char)fminf(255.0f, fmaxf(0.0f, pixel_color.z * 255.0f));
        }
    }
}
