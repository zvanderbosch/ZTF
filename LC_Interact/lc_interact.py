import sys
import numpy as np
from glob import glob
from astropy.io import fits
from astropy.io import ascii
from astropy.table import Table
from astropy.visualization import ZScaleInterval
from astropy.time import Time
from astropy.coordinates import SkyCoord
from astropy import wcs
import matplotlib.pyplot as plt

from bokeh.io import curdoc
from bokeh.layouts import column, row, layout
from bokeh.models import Slider, ColumnDataSource, Button, CustomJS
from bokeh.models import Span, Range1d, LinearColorMapper, Whisker
from bokeh.models.glyphs import Text
from bokeh.plotting import figure

# Load in the ZTF data and convert to Pandas DataFrame
data = Table.read('lc.fits')
data.remove_column('null_bitfield_flags')
data = data.to_pandas()
data['filtercode'] = [x.decode("utf-8") for x in data['filtercode'].values]

# Separate Data into g and r filters and remove
# poor quality epochs with CATFLAGS bit value
gdata = data[(data.filtercode == 'zg') & 
             (data.catflags == 0)].sort_values(by='mjd').reset_index()
rdata = data[(data.filtercode == 'zr') & 
             (data.catflags == 0)].sort_values(by='mjd').reset_index()

# Get RA-Dec
ra = np.average(data.ra.values)
dec = np.average(data.dec.values)
radec = [ra,dec]

# Get data of interest from the loaded lightcurve tables
gmjds = gdata.mjd.values # MJD dates for g-data
rmjds = rdata.mjd.values # MJD dates for r-data
gmags = gdata.mag.values # Magnitudes for g-data
rmags = rdata.mag.values # Magnitudes for r-data
glower = gmags-gdata.magerr.values # Lower Magnitude Errors for g-data
gupper = gmags+gdata.magerr.values # Upper Magnitude Errors for g-data
rlower = rmags-rdata.magerr.values # Lower Magnitude Errors for r-data
rupper = rmags+rdata.magerr.values # Upper Magnitude Errors for r-data

# Get initial ylimits for the light curve plot
ydiff = max(max(gmags),max(rmags)) - min(min(gmags),min(rmags))
ylow = min(min(gmags),min(rmags)) - 0.3*ydiff
yupp = max(max(gmags),max(rmags)) + 0.3*ydiff

# Load in ZTF Images at this object's RA/Dec
ZS = ZScaleInterval(nsamples=10000, contrast=0.15, max_reject=0.5, 
                    min_npixels=5, krej=2.5, max_iterations=5)
fits_files = sorted(glob('ZTF_Sci_Files/*.fits'))
num_files = len(fits_files)
mjds_g,mjds_r = [],[]   # Store MJD of image
imdat_g,imdat_r = [],[] # Store Image pixel data
hdrs_g,hdrs_r = [],[]   # Store Image headers
for f in fits_files:
    hdr = fits.getheader(f)
    dat = fits.getdata(f)
    if hdr['FILTERID'] == 1:
        mjds_g.append(hdr['OBSMJD'])
        imdat_g.append(dat)
        hdrs_g.append(hdr)
    elif hdr['FILTERID'] == 2:
        mjds_r.append(hdr['OBSMJD'])
        imdat_r.append(dat)
        hdrs_r.append(hdr)

# Get max X(columns) and Y(rows) image dimensions
xdim_max = 0
ydim_max = 0
for im in imdat_g:
    if np.shape(im)[0] > xdim_max:
        xdim_max = np.shape(im)[1]
    if np.shape(im)[1] > ydim_max:
        ydim_max = np.shape(im)[0]
xcent = xdim_max/2 # Central X Pixel 
ycent = ydim_max/2 # Central Y Pixel


# Define function to reshape all images to same size
def im_reshape(im,head,xdim,ydim,coord):

    # Initialize new image array filled with zeros
    im_new = np.zeros((xdim,ydim))
    
    # Get shape of current image
    xdim_cur = np.shape(im)[1]
    ydim_cur = np.shape(im)[0]

    # Fill the new image with data values
    im_new[0:ydim_cur,0:xdim_cur] = im

    # Get approximate pixel location of given RA-Dec Coordinates
    w = wcs.WCS(head)
    wpix = w.wcs_world2pix(np.array([coord]),1)
    xpix = wpix[0][0]
    ypix = wpix[0][1]
    xdiff = int(np.round(xcent - xpix))
    ydiff = int(np.round(ycent - ypix))

    # Add zero padding to correct for difference in target
    # locations and then strip data from opposite sides
    if (xdiff >= 0) & (ydiff >= 0):
        im_new = np.pad(im_new,((ydiff,0),(xdiff,0)))
        im_new = im_new[0:ydim,0:xdim]
    elif (xdiff < 0) & (ydiff >= 0):
        im_new = np.pad(im_new,((ydiff,0),(0,abs(xdiff))))
        im_new = im_new[0:ydim,-xdim:]
    elif (ydiff < 0) & (xdiff >= 0):
        im_new = np.pad(im_new,((0,abs(ydiff)),(xdiff,0)))
        im_new = im_new[-ydim:,0:xdim]
    elif (xdiff < 0) & (ydiff < 0):
        im_new = np.pad(im_new,((0,abs(ydiff)),(0,abs(xdiff))))
        im_new = im_new[-ydim:,-xdim:]

    return im_new


# Reshape all of the images to have the same size.
# Fill in empty pixels with NaNs and keep object coordinates 
# centered using the WCS solution for each image.
vmin_g,vmin_r = [],[]   # Store Z-Scale Minimums
vmax_g,vmax_r = [],[]   # Store Z-Scale Maximums

# g-band images
for i,im in enumerate(imdat_g):

    # Get reshaped/centered image
    im_new = im_reshape(im,hdrs_g[i],xdim_max,ydim_max,radec)

    # Calculate new vmin and vmax values (exclude low pixel values)
    vmin,vmax = ZS.get_limits(im_new[im_new > 10.0])
    vmin_g.append(vmin)
    vmax_g.append(vmax)

    # Overwrite old image with new image
    imdat_g[i] = im_new

# Repeat for r-band images
for i,im in enumerate(imdat_r):

    # Get reshaped/centered image
    im_new = im_reshape(im,hdrs_r[i],xdim_max,ydim_max,radec)

    # Calculate new vmin and vmax values (exclude low pixel values)
    vmin,vmax = ZS.get_limits(im_new[im_new > 10.0])
    vmin_r.append(vmin)
    vmax_r.append(vmax)

    # Overwrite old image with new image
    imdat_r[i] = im_new



# Find the Image MJDs which have no associated data points in the light curves
gmjds_nodat = []
rmjds_nodat = []
gmags_all = []
rmags_all = []
gcount = 0
rcount = 0
for i,d in enumerate(mjds_g):
    if min(abs(gdata.mjd.values - d))*86400.0 > 1.0:
        gmjds_nodat.append(d)
        gmags_all.append(ylow+0.10*ydiff)
    else:
        gmags_all.append(gdata.mag.iloc[gcount])
        gcount += 1
for d in mjds_r:
    if min(abs(rdata.mjd.values - d))*86400.0 > 1.0:
        rmjds_nodat.append(d)
        rmags_all.append(ylow+0.10*ydiff)
    else:
        rmags_all.append(rdata.mag.iloc[rcount])
        rcount += 1


# Generate fixed magnitude arrays for images without any light curve data
gmags_nodat = [ylow+0.10*ydiff]*len(gmjds_nodat)
rmags_nodat = [ylow+0.10*ydiff]*len(rmjds_nodat)

# Create CDS objects for light curves
source_g = ColumnDataSource(data=dict(x=gmjds, y=gmags, lower=glower, upper=gupper))
source_r = ColumnDataSource(data=dict(x=rmjds, y=rmags, lower=rlower, upper=rupper))
source_nodat_g = ColumnDataSource(data=dict(x=gmjds_nodat, y=gmags_nodat))
source_nodat_r = ColumnDataSource(data=dict(x=rmjds_nodat, y=rmags_nodat))
g_marker_source = ColumnDataSource(data=dict(x=[mjds_g[0]], y=[gmags_all[0]]))
r_marker_source = ColumnDataSource(data=dict(x=[mjds_r[0]], y=[rmags_all[0]]))


# Generate an object name using the RA/Dec in the Light Curve File
ra = data['ra'].values[0]
de = data['dec'].values[0]
coord = SkyCoord(ra,de,unit="deg",frame="icrs")
coord_str = coord.to_string('hmsdms',sep="",precision=2).replace(" ","")
ztf_name = 'ZTF J{}'.format(coord_str)

# Initialize Light Curve Plot
fig_lc = figure(plot_height=320, plot_width=650,
                tools="pan,wheel_zoom,box_zoom,tap,reset",
                toolbar_location="above", border_fill_color="whitesmoke")
fig_lc.toolbar.logo = None
fig_lc.title.text = "Light Curve for {}".format(ztf_name)
fig_lc.title.offset = -10
fig_lc.yaxis.axis_label = 'Mag'
fig_lc.xaxis.axis_label = 'MJD'
fig_lc.y_range = Range1d(start=yupp, end=ylow)

# Add Error Bars
eg = Whisker(source=source_g, base="x", upper="upper", lower="lower",
             line_color="cornflowerblue",line_width=1.5,line_alpha=0.5)
er = Whisker(source=source_r, base="x", upper="upper", lower="lower",
             line_color="firebrick",line_width=1.5,line_alpha=0.5)
eg.upper_head.line_color = None
eg.lower_head.line_color = None
er.upper_head.line_color = None
er.lower_head.line_color = None
fig_lc.add_layout(eg)
fig_lc.add_layout(er)

# Plot g and r light curve data
fig_lc.square('x', 'y', source=source_g, size=6, 
               # Set defaults
               fill_color="cornflowerblue", line_color="cornflowerblue",
               fill_alpha=0.6, line_alpha=0.6,
               # set visual properties for selected glyphs
               selection_color="cornflowerblue",
               selection_alpha=0.6,
               # set visual properties for non-selected glyphs
               nonselection_color="cornflowerblue",
               nonselection_alpha=0.6)
fig_lc.circle('x', 'y', source=source_r, size=6, 
               # Set defaults
               fill_color="firebrick", line_color="firebrick",
               fill_alpha=0.5, line_alpha=0.5,                    
               # set visual properties for selected glyphs
               selection_color="firebrick",
               selection_alpha=0.5,
               # set visual properties for non-selected glyphs
               nonselection_color="firebrick",
               nonselection_alpha=0.5)

# Plot diamonds for images without any corresponding light curve data
fig_lc.x('x', 'y', source=source_nodat_g, size=7, line_width=1.5,
               # Set defaults
               fill_color="cornflowerblue", line_color="cornflowerblue",
               fill_alpha=0.6, line_alpha=0.6,
               # set visual properties for selected glyphs
               selection_color="cornflowerblue",
               selection_alpha=0.6,
               # set visual properties for non-selected glyphs
               nonselection_color="cornflowerblue",
               nonselection_alpha=0.6)
fig_lc.x('x', 'y', source=source_nodat_r, size=7, line_width=1.5,
               # Set defaults
               fill_color="firebrick", line_color="firebrick",
               fill_alpha=0.5, line_alpha=0.5,                    
               # set visual properties for selected glyphs
               selection_color="firebrick",
               selection_alpha=0.5,
               # set visual properties for non-selected glyphs
               nonselection_color="firebrick",
               nonselection_alpha=0.5)

# Plot Markers for Selected Cadence
fig_lc.square('x','y',source=g_marker_source,
               # Set defaults
               fill_color="black", line_color="black",
               fill_alpha=0, line_alpha=1, line_width=1.5,
               size=12,name='g_marker')
fig_lc.circle('x','y',source=r_marker_source,
               # Set defaults
               fill_color="black", line_color="black",
               fill_alpha=0, line_alpha=1, line_width=1.5,
               size=12,name='r_marker')

# Initialize Image plots
fig_img = figure(plot_width=300, plot_height=320,
                 x_range=[0, imdat_g[0].shape[1]], 
                 y_range=[0, imdat_g[0].shape[0]],
                 title="ZTF-g Image", tools='pan,box_zoom,wheel_zoom,reset',
                 toolbar_location="above",
                 border_fill_color="whitesmoke")
fig_imr = figure(plot_width=300, plot_height=320,
                 x_range=fig_img.x_range, 
                 y_range=fig_img.y_range,
                 title="ZTF-r Image", tools='pan,box_zoom,wheel_zoom,reset',
                 toolbar_location="above",
                 border_fill_color="whitesmoke")
fig_img.toolbar.logo = None
fig_imr.toolbar.logo = None

# Create Z-Scale Normalized Color Maps
color_mapper_g = LinearColorMapper(palette="Greys256", low=vmin_g[0], high=vmax_g[0])
color_mapper_r = LinearColorMapper(palette="Greys256", low=vmin_r[0], high=vmax_r[0])
# Plot the images
fig_img.image(image=[imdat_g[0]], x=0, y=0, dw=imdat_g[0].shape[1], dh=imdat_g[0].shape[0], 
              dilate=True, color_mapper=color_mapper_g, name="gframe")
fig_imr.image(image=[imdat_r[0]], x=0, y=0, dw=imdat_r[0].shape[1], dh=imdat_r[0].shape[0], 
              dilate=True, color_mapper=color_mapper_r, name="rframe")


# Interactive slider widgets and buttons to select the image number
g_frame_slider = Slider(start=1,end=len(imdat_g),
                        value=1,step=1,bar_color='cornflowerblue',
                        title="g-Frame Slider",width=520,
                        value_throttled=200,
                        background="whitesmoke")
r_frame_slider = Slider(start=1,end=len(imdat_r),
                        value=1,step=1,bar_color='firebrick',
                        title="r-Frame Slider",width=520,
                        value_throttled=200,
                        background="whitesmoke")
rbutton_g = Button(label=">", button_type="default", width=40)
lbutton_g = Button(label="<", button_type="default", width=40)
rbutton_r = Button(label=">", button_type="default", width=40)
lbutton_r = Button(label="<", button_type="default", width=40)


# Initialize the Info Box Plots
fig_infog = figure(plot_width=325, plot_height=222,
                   x_range=[0, 1], y_range=[0, 1],
                   title="ZTF-g Image MetaData", tools='',
                   border_fill_color="whitesmoke")
fig_infor = figure(plot_width=325, plot_height=222,
                   x_range=[0, 1], y_range=[0, 1],
                   title="ZTF-r Image MetaData", tools='',
                   border_fill_color="whitesmoke")
fig_infog.toolbar.logo = None
fig_infor.toolbar.logo = None

# Configure Info Box appearance
fig_infog.xgrid.visible = False # Remove x grid
fig_infog.ygrid.visible = False # Remove y grid
fig_infor.xgrid.visible = False # Remove x grid
fig_infor.ygrid.visible = False # Remove y grid
fig_infog.xaxis.visible = False # Remove x-axis
fig_infog.yaxis.visible = False # Remove y-axis
fig_infor.xaxis.visible = False # Remove x-axis
fig_infor.yaxis.visible = False # Remove y-axis
fig_infog.title.align = "center" # Put title in center
fig_infor.title.align = "center" # Put title in center

# Function to generate text output
text_formats = ['Date-Time : {}',
                '      MJD : {:.6f}',
                '  Airmass : {:.3f}',
                '   Seeing : {:.3f}"',
                'Mag Limit : {:.2f}',
                'Moon Frac : {:.3f}',
                '     Temp : {:.1f} C',
                '     Wind : {:.1f} mph',
                ' Humidity : {:.0f} %',
                ' Infobits : {:.0f}']
hdr_keys = ['OBSMJD','OBSMJD','AIRMASS','SEEING','MAGLIM',
            'MOONILLF','TEMPTURE','WINDSPD','HUMIDITY','INFOBITS']
def gen_text(h):
    text_output = []
    for i in range(len(text_formats)):
        if i == 0:
            t = Time(h[hdr_keys[i]],scale='utc',format='mjd')
            text = text_formats[i].format(t.iso)
        else:
            text = text_formats[i].format(abs(h[hdr_keys[i]]))
        text_output.append(text)
    return text_output

# Generate text Glyphs
xlocs = [0.03]*10  # x-locations for each line of text
ylocs = [0.89 - float(i)*0.09 for i in range(10)] # y-locations for each line of text
text_init_g = gen_text(hdrs_g[0])  # Initial g-frame info to display
text_init_r = gen_text(hdrs_r[0])  # Initial r-frame info to display
text_source_g = ColumnDataSource(data=dict(xloc=xlocs,yloc=ylocs,text=text_init_g))
text_source_r = ColumnDataSource(data=dict(xloc=xlocs,yloc=ylocs,text=text_init_r))
textglyph_g = Text(x="xloc", y="yloc", text="text", 
                   text_font='courier', text_font_size='9pt')
textglyph_r = Text(x="xloc", y="yloc", text="text", 
                   text_font='courier', text_font_size='9pt')
fig_infog.add_glyph(text_source_g, textglyph_g)
fig_infor.add_glyph(text_source_r, textglyph_r)


# Callback function for g-frame slider
def update_g_frame(attr, old, new):
    newind = new
    fig_img.select('gframe')[0].data_source.data['image'] = [imdat_g[newind-1]]
    fig_img.select('gframe')[0].glyph.color_mapper.high = vmax_g[newind-1]
    fig_img.select('gframe')[0].glyph.color_mapper.low = vmin_g[newind-1]
    g_marker_source.data = dict(x=[mjds_g[newind-1]],y=[gmags_all[newind-1]])

    # Update text
    new_text = gen_text(hdrs_g[newind-1])
    text_source_g.data["text"] = new_text

    # Clear selections
    source_g.selected.indices = []
    source_nodat_g.selected.indices = []

# Callback function for r-frame slider
def update_r_frame(attr, old, new):
    newind = new
    fig_imr.select('rframe')[0].data_source.data['image'] = [imdat_r[newind-1]]
    fig_imr.select('rframe')[0].glyph.color_mapper.high = vmax_r[newind-1]
    fig_imr.select('rframe')[0].glyph.color_mapper.low = vmin_r[newind-1]
    r_marker_source.data = dict(x=[mjds_r[newind-1]],y=[rmags_all[newind-1]])

    # Update text
    new_text = gen_text(hdrs_r[newind-1])
    text_source_r.data["text"] = new_text

    # Clear selections
    source_r.selected.indices = []
    source_nodat_r.selected.indices = []

# Right button click event for g-frame
def go_right_by_one_gframe():
    existing_value = g_frame_slider.value
    if existing_value < len(imdat_g):
        g_frame_slider.value = existing_value + 1

# Left button click event for g-frame
def go_left_by_one_gframe():
    existing_value = g_frame_slider.value
    if existing_value > 1:
        g_frame_slider.value = existing_value - 1

# Right button click event for r-frame
def go_right_by_one_rframe():
    existing_value = r_frame_slider.value
    if existing_value < len(imdat_r):
        r_frame_slider.value = existing_value + 1

# Left button click event for r-frame
def go_left_by_one_rframe():
    existing_value = r_frame_slider.value
    if existing_value > 1:
        r_frame_slider.value = existing_value - 1

# Callback function which moves slider when a
# data point is clicked on in the Light Curve plot
def jump_to_lightcurve_position(event):
    if source_g.selected.indices != []:
        num_lower = np.count_nonzero(source_nodat_g.data['x'] < 
                                     source_g.data['x'][source_g.selected.indices[0]])
        g_frame_slider.value = source_g.selected.indices[0]+num_lower+1
    if source_r.selected.indices != []:
        num_lower = np.count_nonzero(source_nodat_r.data['x'] < 
                                     source_r.data['x'][source_r.selected.indices[0]])
        r_frame_slider.value = source_r.selected.indices[0]+num_lower+1
    if source_nodat_g.selected.indices != []:
        num_lower = np.count_nonzero(source_g.data['x'] < 
                                     source_nodat_g.data['x'][source_nodat_g.selected.indices[0]])
        g_frame_slider.value = source_nodat_g.selected.indices[0]+num_lower+1
    if source_nodat_r.selected.indices != []:
        num_lower = np.count_nonzero(source_r.data['x'] < 
                                     source_nodat_r.data['x'][source_nodat_r.selected.indices[0]])
        r_frame_slider.value = source_nodat_r.selected.indices[0]+num_lower+1

# Connect different objects/events to callback functions
rbutton_g.on_click(go_right_by_one_gframe)
lbutton_g.on_click(go_left_by_one_gframe)
rbutton_r.on_click(go_right_by_one_rframe)
lbutton_r.on_click(go_left_by_one_rframe)
fig_lc.on_event('tap',jump_to_lightcurve_position)

# Connect callback to the sliders
g_frame_slider.on_change('value',update_g_frame)
r_frame_slider.on_change('value',update_r_frame)


# Create plot grid
l = layout([fig_lc,fig_img],
           [column(row(lbutton_g,rbutton_g,g_frame_slider),
                   row(lbutton_r,rbutton_r,r_frame_slider),
                   row(fig_infog,fig_infor)),fig_imr])

# Add everything into the Bokeh document
curdoc().add_root(l)
