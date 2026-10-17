Theodore Object3D Lab
======================

Test the Intel RealSense and the Luxonis OAK-D, then the recognition
questions (distance, animal, food, maker, year, signs, heat, smell, touch).
The synthetic bench does not need a camera. Live capture does.

Tools you can use
-----------------
This lab (browser, port 8020)
  The camera stays on. Color and depth are large and aligned. Image controls
  (exposure, white balance, CLAHE, sharpen) and depth controls (preset, laser,
  hole fill, near/far) sit under the pictures. Ask and enroll use the live frame.
  Command:
    PYTHONPATH=subrepos/theodore_object3d_lab/src:packages/shared/src \
      python3 -m uvicorn theodore_object3d_lab.main:app --port 8020 --host 127.0.0.1
  Open http://127.0.0.1:8020/

scripts/object3d_pipeline.py
  One scan. --camera realsense, oak, or both. --detector depth, coco, or auto.

scripts/object3d_ask.py
  Ask one question of the live camera, or pass --sign and --no-camera.

scripts/object3d_train.py
  Enroll many labeled folders with parallel workers. Optional --celsius,
  --smell, --texture, --sensors reading.json, --thermal thermal.npy.

Intel RealSense Viewer (realsense-viewer)
  Official color, infrared, and depth viewer. It comes with a graphical
  librealsense build. This Spark has the pyrealsense2 wheel, which streams
  frames and does not include that viewer. Use this lab or object3d_pipeline.py
  for aligned metric depth.

v4l2-ctl and ffplay
  ffplay /dev/video0 shows a RealSense UVC node. That is not aligned depth.

Luxonis DepthAI demo
  depthai_demo.py from the depthai-python examples, or the DepthAI Viewer app.
  This lab already uses the installed depthai package. Oak stereo depth needs
  a USB 3 cable; on USB 2 the lab still returns color.

STEP BY STEP (from repo root)
-----------------------------

  cd "$(git rev-parse --show-toplevel)"
  . .venv/bin/activate

  PYTHONPATH=subrepos/theodore_object3d_lab/src:packages/shared/src \
    python3 -m pytest subrepos/theodore_object3d_lab/tests -q

  PYTHONPATH=subrepos/theodore_object3d_lab/src:packages/shared/src \
    python3 -m uvicorn theodore_object3d_lab.main:app --port 8020 --host 127.0.0.1

  curl -s http://127.0.0.1:8020/health
  curl -s -X POST http://127.0.0.1:8020/api/object3d/bench
  curl -s http://127.0.0.1:8020/api/object3d/devices
  curl -s -X POST http://127.0.0.1:8020/api/object3d/live/start \
    -H 'content-type: application/json' \
    -d '{"camera":"realsense","quality":"clear"}'
  curl -s http://127.0.0.1:8020/api/object3d/live/status

The bench must report ok=true. Devices lists the RealSense serial and the
OAK MXID when those cameras are plugged in. Open the page and the RealSense
starts on its own. Clear tries 1280x720, then 640x480 if the USB link cannot
carry it. The depth picture keeps the color frame where there is no return,
so a sparse map is not a black cutout. Distance still uses measured pixels.

API
---
  GET  /  and /lab
  GET  /health
  GET  /api/object3d/devices
  GET  /api/object3d/tools
  POST /api/object3d/bench
  GET  /api/object3d/live/status
  GET  /api/object3d/live/frame.jpg?view=color|depth
  POST /api/object3d/live/start    {camera, quality}
  POST /api/object3d/live/stop
  POST /api/object3d/live/controls {brightness, laser, clahe, preset, ...}
  POST /api/object3d/live/reset
  POST /api/object3d/capture     {camera, detector, question}
  POST /api/object3d/ask         {question, sign, target}
  POST /api/object3d/enroll      {label, maker, year, celsius, smell, texture, camera, detector}

Enroll with an empty camera uses the synthetic frame. Enroll with
camera=realsense uses the live nearest object. The gallery lasts for the
lab process. Heat, smell, and touch stay empty until a reading is enrolled
or a sensor bundle is attached.
