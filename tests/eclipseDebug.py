from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
# Put in whatever code you want to use for an eclipse debug run here...


#mayapy -c "import pymel.core as pm; plug='stereoCamera'; pm.loadPlugin(plug) if not pm.pluginInfo(plug, loaded=1, q=1) else 'doNothing'; print '*******loaded******'; pm.unloadPlugin(plug, f=1); print '*****unloaded*******'"

from builtins import *
from __builtin__ import str
import pymel.core as pm
node = pm.nt.Transform('persp')
attr = node.attr('translate')
attr.set( (1,2,3) )
