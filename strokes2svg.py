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
   
    svg = '<svg xmlns="http://www.w3.org/2000/svg" version="1.1">\n'

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
        layerCode.append( '\t<g id="%s" transform-origin="50%% 50%%" transform="scale(1.0 -1.0)" opacity="%f" visibility="%s" style="fill: none; stroke: black; stroke-width:1px;">\n' % (
                layer[ "name" ],
                layer[ "opacity" ],
                'visible' if layer[ 'visible' ] else 'hidden'
        ))
        layerIdx += 1
    
    matrix = np.matrix(np.eye(4))
    matrix_flat = ', '.join(str(v) for v in matrix.A1)
    
    # Pen state
    penColor = [ 0.0, 0.0, 0.0 ]
    penAlpha = 1.0
    penSize  = 1.0
    isEraser = False
    
    # Go through all the actions in the mischief file
    for action in artFile.actions:
        if action['action_name'] == 'paste_layer':
            print('<!-- paste layer used, the result may be invalid! -->')
        # Set pen matrix action
        if action['action_id'] == 51:
            layer_matrix = np.matrix(artFile.layers[action['layer']]['matrix'])
            pen_matrix   = np.matrix(action['matrix'])
            matrix       = layer_matrix * pen_matrix
            matrix_flat = ', '.join(str(v) for v in matrix.A1)
        
        # Stroke Action
        elif action[ 'action_id' ] == 1 or action['action_name'] == 'polyline':
            layerIdx = action[ 'layer' ]
            assert( layerCode[ layerIdx ] != None )

            # CSS that goes into the polyline's style attribute
            css = ''
            
            if isEraser:
                css += 'stroke: white; '
            else:
                css += 'stroke: rgb(%f, %f, %f); ' % ( penColor[ 0 ], penColor[ 1 ], penColor[ 2 ] )
        
            # If pen size is not one (the default we set in the <g> tag),
            # specify the size
            if not isEqual( penSize, 1.0 ):
                css += 'stroke-width: %fpx; ' % penSize
        
            # If pen opacity is not 100%, specify that in the CSS
            if not isEqual( penAlpha, 1.0 ):
                css += 'stroke-opacity: %f; ' % penAlpha
        
            css += 'stroke-linejoin: round; '
            css += 'stroke-linecap: round; '
            css += 'transform: matrix3d({}); '.format(matrix_flat)

            # If there is any CSS to add, set this to 'style="..."', otherwise
            # set it to an empty string. That way we don't add an empty style
            # attribute where there is nothing to set.
            styleAttr = ''
            if len(css) > 0:
                styleAttr = 'style="%s" ' % css
            
            layerCode[ layerIdx ] += '\t\t<polyline %spoints="' % styleAttr
            
            # Output stroke points
            for point in action[ 'points' ]:
                layerCode[ layerIdx ] += str( point['x'] ) + "," + str( point['y'] ) + " "

            layerCode[ layerIdx ] += '" />\n'
    
        # Set Pen Color Action
        elif action[ 'action_id' ] == 0x35:
            penColor = action[ 'color' ]
        
        # Set Pen Properties Action
        elif action[ 'action_id' ] == 0x34:
            penSize  = action[ 'size'    ]
            penAlpha = action[ 'opacity' ]

        elif action['action_name'] == 'is_eraser':
            isEraser = action['is_eraser']

        elif action['action_name'] == 'rect':
            layerIdx = action[ 'layer' ]
            (x, y) = (action['x'], action['y'])
            (w, h) = (action['w'], action['h'])
            angle = action['angle']
            style = "stroke: rgb({}, {}, {});".format(penColor[0], penColor[1], penColor[2]);
            style += 'border-radius: {}px; '.format(penSize)
            style += 'stroke-width: {}px; '.format(penSize)
            style += 'stroke-opacity: {}; '.format(penAlpha)
            style += 'stroke-linejoin: round; '
            style += "transform-origin: 0 0;"

            tx = -w / 2.0
            ty = -h / 2.0
            style += ("transform: matrix3d({}) translate({}px, {}px) rotate({}deg) translate({}px, {}px)"
                    .format(matrix_flat, x, y, angle, tx, ty))
            layerCode[layerIdx] += (
                '\t\t<rect x="0" y="0" width="{}" height="{}" style="{}" />\n'
                    .format(w, h, style))

        elif action['action_name'] == 'ellipse':
            layerIdx = action[ 'layer' ]
            (cx, cy) = (action['cx'], action['cy'])
            (rx, ry) = (action['rx'], action['ry'])
            angle = action['angle']
            matrix_flat = ', '.join(str(v) for v in matrix.A1)
            style = "stroke: rgb({}, {}, {});".format(penColor[0], penColor[1], penColor[2]);
            style += 'border-radius: {}px; '.format(penSize)
            style += 'stroke-width: {}px; '.format(penSize)
            style += 'stroke-opacity: {}; '.format(penAlpha)
            style += 'stroke-linejoin: round; '
            style += "transform-origin: 0 0;"

            tx = -rx / 2.0
            ty = -ry / 2.0
            style += ("transform: matrix3d({}) translate({}px, {}px) rotate({}deg) translate({}px, {}px)"
                    .format(matrix_flat, cx, cy, angle, tx, ty))
            layerCode[layerIdx] += (
                '\t\t<ellipse cx="0" cy="0" rx="{}" ry="{}" style="{}" />\n'
                    .format(rx, ry, style))

        elif action['action_name'] == 'pen_matrix':
            layerIdx = action[ 'layer' ]
            (cx, cy) = (action['cx'], action['cy'])
            (rx, ry) = (action['rx'], action['ry'])

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
