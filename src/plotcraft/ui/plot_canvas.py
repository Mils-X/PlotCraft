from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from plotcraft.core.plotting import make_bar_figure
from plotcraft.core.style import PlotStyle


class PlotCanvas(FigureCanvasQTAgg):
    def __init__(self) -> None:
        super().__init__(Figure(figsize=(6, 4.5), dpi=100))

    def draw_plot(self, data: dict[str, list[float]], style: PlotStyle) -> None:
        make_bar_figure(data, style, self.figure)
        self.draw_idle()
