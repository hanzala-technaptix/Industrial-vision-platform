import time

class FPSCounter:
    """
    Calculates the actual performance rate of the AI pipeline.
    """
    def __init__(self):
        self.p_time = 0
        
    def get_fps(self):
        c_time = time.time()
        fps = 1 / (c_time - self.p_time) if (c_time - self.p_time) > 0 else 0
        self.p_time = c_time
        return int(fps)
