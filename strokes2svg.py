import sys
import numpy as np
import artparser

# Compare two floats with a given tolerance. This is how it's done in C++,
# if Python has a better way we should use that.
# More precision won't show up in the svg anyway due to how format strings work
# by default.
def isEqual( a, b ):
    return abs( a - b ) < 10.0e-6

def buildSvg( artFile ):
   
    svg = "<svg>\n"

    # If the background isn't white, add a full-size rectangle of the
    # given color
    if not isEqual( artFile.background_color[ 0 ], 1.0 ) or \
       not isEqual( artFile.background_color[ 1 ], 1.0 ) or \
       not isEqual( artFile.background_color[ 2 ], 1.0 ):
       svg += '\t<rect id="mischiefBg" width="100%%" height="100%%" style="stroke: none; fill:rgb(%f, %f, %f);"/>\n' % artFile.background_color
    
    # A list of strings, each holding the SVG code for one of the layers.
    # Actions are recorded in creation sequence and not stored per-layer,
    # so we need to go through all actions and append the corresponding code
    # to the svg for the layer they are associated with and then combine the
    # layers in the end.
    layerCode = []
    
    # Start each layer with a g (group) tag
    layerIdx = 0
    for layer in artFile.layers:
        # Add a new block of code to the list
        # FIXME: The id attribute probably shouldn't have spaces in it, and
        # if the layer name has any quotes in it, we're in deep trouble!
        # But what is the correct way to export a layer name? Affinity Designer
        # seems to use the id attribute value as a layer name.
        layerCode.append( '\t<g id="%s" transform="scale(1.0 -1.0)" opacity="%f" visibility="%s" style="fill: none; stroke: black; stroke-width:1px;">\n' % (
                layer[ "name" ],
                layer[ "opacity" ],
                'visible' if layer[ 'visible' ] else 'hidden'
        ))
        layerIdx += 1
    
    matrix = np.eye(4)
    
    # Pen state
    penColor = [ 0.0, 0.0, 0.0 ]
    penAlpha = 1.0
    penSize  = 1.0
    
    # Go through all the actions in the mischief file
    for action in artFile.actions:
        
        # Set pen matrix action
        if action['action_id'] == 51:
            layer_matrix = np.matrix(artFile.layers[action['layer']]['matrix'])
            pen_matrix   = np.matrix(action['matrix'])
            matrix       = layer_matrix * pen_matrix
        
        # Stroke Action
        elif action[ 'action_id' ] == 1:
            layerIdx = action[ 'layer' ]
            assert( layerCode[ layerIdx ] != None )

            # CSS that goes into the polyline's style attribute
            css = ''
            
            # If any of the color components is non-zero, output a color.
            # We don't need to write black since we specified that as the
            # default in the <g> tag for the layer
            if not isEqual( penColor[ 0 ], 0.0 ) or not isEqual( penColor[ 1 ], 0.0 ) or not isEqual( penColor[ 2 ], 0.0 ):
                css += 'stroke: rgb(%f, %f, %f); ' % ( penColor[ 0 ], penColor[ 1 ], penColor[ 2 ] )
        
            # If pen size is not one (the default we set in the <g> tag),
            # specify the size
            if not isEqual( penSize, 1.0 ):
                css += 'stroke-width: %fpx; ' % penSize
        
            # If pen opacity is not 100%, specify that in the CSS
            if not isEqual( penAlpha, 1.0 ):
                css += 'stroke-opacity: %f; ' % penAlpha
        
            # If there is any CSS to add, set this to 'style="..."', otherwise
            # set it to an empty string. That way we don't add an empty style
            # attribute where there is nothing to set.
            styleAttr = ''
            if len(css) > 0:
                styleAttr = 'style="%s" ' % css
            
            layerCode[ layerIdx ] += '\t\t<polyline %spoints="' % styleAttr
            
            # Output stroke points
            for point in action[ 'points' ]:
                vec = np.array([point['x'], point['y'], 0, 1])
                vec = vec * matrix
                layerCode[ layerIdx ] += str( vec[0,0] ) + "," + str( vec[0,1] ) + " "

            layerCode[ layerIdx ] += '" />\n'
    
        # Set Pen Color Action
        elif action[ 'action_id' ] == 0x35:
            penColor = action[ 'color' ]
        
        # Set Pen Properties Action
        elif action[ 'action_id' ] == 0x34:
            penSize  = action[ 'size'    ]
            penAlpha = action[ 'opacity' ]
        
        # Ignore all other actions for now
        else:
            pass

    # Now that we built the code for the individual layers,
    # combine them into the final SVG
    for code in layerCode:
        # FIXME: This won't change the code for the layer since "code" is a
        # temporary copy. Doesn't matter since we add that temporary copy to the
        # output SVG, but I should probably learn Python at some point and
        # figure out how to actually do this correctly.
        code += "\t</g>\n"
        svg += code
    
    svg += "</svg>\n"
    
    return svg
    
    
def main( argv ):
	artFile = artparser.ArtParser( argv[ 1 ] )
	print(buildSvg( artFile ))

if __name__ == '__main__':
	sys.exit( main( sys.argv ) )
