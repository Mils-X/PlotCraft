from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class PlotCanvas(FigureCanvasQTAgg):
    def __init__(self) -> None:
        super().__init__(Figure(figsize=(6, 4.5), dpi=100))
        self.setMinimumSize(300, 220)

    def draw_with(self, builder) -> None:
        """builder(fig) dibuja en la figura del lienzo (sin imponer tamaño)."""
        builder(self.figure)
        self.draw_idle()
