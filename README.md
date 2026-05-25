# RayTracer Custom Engine

A custom ray tracing engine built from scratch. The core rendering pipeline is written in C for CPU efficiency, and the graphical user interface and scene management are built with Python and PyQt5.

## Features

* **Ray Tracing:** Calculates shadows, diffuse lighting, and recursive reflections.
* **C Engine & OpenMP:** The backend is written in C and uses OpenMP for multi-core CPU processing.
* **Viewport Controls:** First-person camera movement using keyboard and mouse inputs.
* **Scene Management:** Add, modify, or remove spheres, planes, and point lights through the UI. Adjust position, color, radius, light power, and reflectivity.
* **Save/Load:** Export and import scene configurations as `.json` files.

## Prerequisites

To compile and run this project, you need a C compiler and Python installed.

1. **GCC (GNU Compiler Collection)**
2. **Python 3.x**
3. **Python Packages:**
   pip install numpy PyQt5

## Installation & Build Instructions
**1.Clone The Repository:** 
    git clone [https://github.com/aliarhanila/RayTracer-CustomEngine.git](https://      github.com/aliarhanila/RayTracer-CustomEngine.git)
    cd RayTracer-CustomEngine

**2. Compile the C Engine:**
   gcc -shared -o libengine.so -fPIC engine.c -O3 -ffast-math -fopenmp

**3. Run the Application:**
python run_gui.py

## Controls

Hold Right-Click + Move Mouse: Look around  

W / S: Move Forward / Backward  

A / D: Move Left / Right  

Space / Shift: Move Up / Down  


# Project Structure

   engine.c: Handles all mathematical operations, ray-object intersections, and light calculations.  
   
   render/renderer.py: Acts as a bridge using ctypes to pass data between Python and the compiled C library.  
   
   gui/gui_qt.py: Contains the PyQt5 frontend, input handling, game loop, and JSON serialization logic
