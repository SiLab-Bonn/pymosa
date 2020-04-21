import numpy as np
from matplotlib import colors, cm
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from mpl_toolkits.axes_grid1 import make_axes_locatable


def plot_occupancy(hist, title='Occupancy', z_label='# of hits', z_min=None, z_max=None, output_pdf=None):
    if z_max == 'median':
        z_max = 2 * np.ma.median(hist)
    elif z_max == 'maximum':
        z_max = np.ma.max(hist)
    elif z_max is None:
        z_max = np.percentile(hist, q=90)
        if np.any(hist > z_max):
            z_max = 1.1 * z_max
    if z_max < 1 or hist.all() is np.ma.masked:
        z_max = 1.0

    if z_min is None:
        z_min = np.ma.min(hist)
    if z_min == z_max or hist.all() is np.ma.masked:
        z_min = 0

    fig = Figure()
    FigureCanvas(fig)
    ax = fig.add_subplot(111)

    ax.set_adjustable('box')
    extent = [0.5, 1152.5, 576.5, 0.5]
    bounds = np.linspace(start=z_min, stop=z_max + 1, num=255, endpoint=True)
    cmap = cm.get_cmap('plasma')
    cmap.set_bad('w')
    cmap.set_over('r')  # Make noisy pixels red
    norm = colors.BoundaryNorm(bounds, cmap.N)

    im = ax.imshow(hist, interpolation='none', aspect='equal', cmap=cmap, norm=norm, extent=extent)  # TODO: use pcolor or pcolormesh
    ax.set_ylim((576.5, 0.5))
    ax.set_xlim((0.5, 1152.5))
    ax.set_title(title + r' ($\Sigma$ = {0})'.format((0 if hist.all() is np.ma.masked else np.ma.sum(hist))))
    ax.set_xlabel('Column')
    ax.set_ylabel('Row')

    divider = make_axes_locatable(ax)
    pad = 0.6

    cax = divider.append_axes("bottom", size="5%", pad=pad)
    cb = fig.colorbar(im, cax=cax, ticks=np.linspace(start=z_min, stop=z_max, num=10, endpoint=True), orientation='horizontal')
    cax.set_xticklabels([int(round(float(x.get_text().replace('\u2212', '-').encode('utf8')))) for x in cax.xaxis.get_majorticklabels()])
    cb.set_label(z_label)
    output_pdf.savefig(fig, bbox_inches='tight')


def plot_noise_tuning_result(fake_hit_rate, fake_hit_rate_spec=None, output_pdf=None):
    cmap = cm.get_cmap('tab20c')
    colors = [cmap.colors[0], cmap.colors[1], cmap.colors[2], cmap.colors[3]]
    markers = ['o', 's', 'p', 'P', '^', '*']
    fig = Figure()
    FigureCanvas(fig)
    ax = fig.add_subplot(111)
    for plane in range(6):
        for region in range(4):
            ax.plot(fake_hit_rate[:, plane, region], ls='--', marker=markers[plane], color=colors[region])
    if fake_hit_rate_spec is not None:
        ax.axhline(fake_hit_rate_spec, color='grey', ls='--', lw=1.5)
    ax.set_yscale('log')
    ax.set_ylabel('Average fake hit rate / pixel / 115.2 us')
    ax.set_xlabel('Iteration')
    ax.grid()
    output_pdf.savefig(fig, bbox_inches='tight')
