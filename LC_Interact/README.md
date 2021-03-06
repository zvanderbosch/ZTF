## A Bokeh-based Light Curve and Image Inspection Tool (lc_interact.py)

This python script generates a web application running on a Bokeh server which allows for the visual inspection of ZTF light curves and images for a single object.

As input this script requires a ZTF lightcurve file named **lc.fits** and a folder named **ZTF_Sci_Files** containing all of the science images in FITS format.  These are the default names provided when light curves and images are downloaded from the [NASA/IPAC Infrared Science Archive](https://irsa.ipac.caltech.edu/Missions/ztf.html). 

From the folder containing your light curve and image data, you can run this app from the command line with:

```
bokeh serve --show lc_interact.py
```

This should automatically launch the server which will take a few seconds to load, depending on how much data you are loading into the application.


This app has the following dependencies:

* Python 3.5 or later
* Astropy
* Bokeh

If properly loaded, the application should look like the following:

![Screenshot Image](./images/lc_interact_screenshot.png)

In the light curve plot, red circles (r-band) and blue squares (g-band) represent data which have both good quality light curve detections and ZTF science images.  Blue and red X's represent the time-locations of images which do not have corresponding light curve data points, most likely due to low photometric quality of the images.

In addition, this application only shows light curve data points which have *catflags=0*, a condition recommended in the [ZTF Science Data System Explanatory Supplement](http://web.ipac.caltech.edu/staff/fmasci/ztf/ztf_pipelines_deliverables.pdf) for clean light curves.
