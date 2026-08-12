import cv2 
import time 


import threading

class VideoStream():
    def __init__(self, source=0):
        self.source = source 
        self.cap = None
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.thread = None

    def connect(self):
        self.cap = cv2.VideoCapture(self.source)
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._update, daemon=True)
            self.thread.start()

    def _update(self):
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                time.sleep(1)
                continue
            
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame
            else:
                with self.lock:
                    self.frame = None
                print("Failed to read frame")

    def get_frame(self):
        if self.cap is None or not self.cap.isOpened():
            print("Reconnecting to camera")
            self.connect()
            time.sleep(1)

        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
            return None

    def release(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
        
if __name__ == "__main__":
    stream = VideoStream(0)

    while True:
        frame = stream.get_frame()

        if frame is None:
            continue

        cv2.imshow("test", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    stream.release()
    cv2.destroyAllWindows()


import cv2
print(cv2)
print(dir(cv2))