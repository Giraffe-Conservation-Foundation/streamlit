"""
Test script to demonstrate different arrow/line options for Plotly Mapbox
Shows various approaches to display directional arrows on maps
"""

import plotly.graph_objects as go
import numpy as np

# Sample coordinates (Botswana to South Africa)
origin_lat, origin_lon = -22.24, 25.33  # Botswana
dest_lat, dest_lon = -26.77, 24.58      # South Africa

fig = go.Figure()

# ============================================
# OPTION 1: Simple line (what we have now)
# ============================================
fig.add_trace(go.Scattermapbox(
    lat=[origin_lat, dest_lat],
    lon=[origin_lon, dest_lon],
    mode='lines',
    line=dict(width=3, color='red'),
    name='Option 1: Simple line (no arrow)'
))

# ============================================
# OPTION 2: Line with markers at ends
# ============================================
# Origin marker (small white circle)
fig.add_trace(go.Scattermapbox(
    lat=[origin_lat],
    lon=[origin_lon],
    mode='markers',
    marker=dict(size=10, color='lightblue', symbol='circle'),
    name='Option 2: Small origin'
))

# Destination marker (large blue circle)
fig.add_trace(go.Scattermapbox(
    lat=[dest_lat],
    lon=[dest_lon],
    mode='markers',
    marker=dict(size=16, color='blue', symbol='circle'),
    name='Option 2: Large destination'
))

# ============================================
# OPTION 3: Line with triangular arrow head
# ============================================
# Calculate angle for arrow
dx = dest_lon - origin_lon
dy = dest_lat - origin_lat
angle = np.arctan2(dy, dx)

# Create arrow head triangle
arrow_length = 0.3  # degrees
arrow_width = 0.15  # degrees

# Arrow back point
arrow_back_lat = dest_lat - arrow_length * np.sin(angle)
arrow_back_lon = dest_lon - arrow_length * np.cos(angle)

# Arrow wings
left_lat = arrow_back_lat - arrow_width * np.cos(angle)
left_lon = arrow_back_lon + arrow_width * np.sin(angle)

right_lat = arrow_back_lat + arrow_width * np.cos(angle)
right_lon = arrow_back_lon - arrow_width * np.sin(angle)

# Offset for option 3 display
offset = 0.5
fig.add_trace(go.Scattermapbox(
    lat=[origin_lat + offset, dest_lat + offset],
    lon=[origin_lon, dest_lon],
    mode='lines',
    line=dict(width=3, color='green'),
    name='Option 3: With triangle arrow',
    showlegend=False
))

fig.add_trace(go.Scattermapbox(
    lat=[dest_lat + offset, left_lat + offset, right_lat + offset, dest_lat + offset],
    lon=[dest_lon, left_lon, right_lon, dest_lon],
    mode='lines',
    fill='toself',
    fillcolor='green',
    line=dict(width=1, color='darkgreen'),
    name='Option 3: Triangle head',
    showlegend=False
))

# ============================================
# OPTION 4: Dashed line with end markers
# ============================================
fig.add_trace(go.Scattermapbox(
    lat=[origin_lat - offset, dest_lat - offset],
    lon=[origin_lon, dest_lon],
    mode='lines',
    line=dict(width=3, color='purple', dash='dash'),
    name='Option 4: Dashed line'
))

fig.add_trace(go.Scattermapbox(
    lat=[dest_lat - offset],
    lon=[dest_lon],
    mode='markers',
    marker=dict(size=20, color='purple', symbol='triangle',
               angle=np.degrees(angle)),
    name='Option 4: Triangle marker',
    showlegend=False
))

# ============================================
# OPTION 5: Thick gradient line with circles
# ============================================
fig.add_trace(go.Scattermapbox(
    lat=[origin_lat, dest_lat],
    lon=[origin_lon + offset, dest_lon + offset],
    mode='lines+markers',
    line=dict(width=4, color='orange'),
    marker=dict(
        size=[12, 20],  # Small at origin, large at destination
        color=['lightyellow', 'orange']
    ),
    name='Option 5: Gradient markers'
))

# ============================================
# OPTION 6: Line with arrow symbols at intervals
# ============================================
# Create points along the line
t = np.linspace(0, 1, 5)
lats = origin_lat - offset * 2 + (dest_lat - origin_lat) * t
lons = origin_lon + (dest_lon - origin_lon) * t

fig.add_trace(go.Scattermapbox(
    lat=lats,
    lon=lons,
    mode='lines+markers',
    line=dict(width=3, color='brown'),
    marker=dict(size=15, symbol='triangle', color='brown',
               angle=np.degrees(angle)),
    name='Option 6: Arrow symbols'
))

# Map layout
fig.update_layout(
    mapbox=dict(
        style="open-street-map",
        zoom=4.5,
        center=dict(lat=-24.5, lon=25)
    ),
    height=800,
    title="Arrow Options Test - Different ways to show direction on map<br>" +
          "<sub>Option 1: Simple line | Option 2: Size difference | Option 3: Triangle head | " +
          "Option 4: Triangle marker | Option 5: Gradient | Option 6: Multiple arrows</sub>",
    showlegend=True,
    legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="left",
        x=0.01,
        bgcolor="rgba(255,255,255,0.8)"
    )
)

print("Opening preview in browser...")
print("\nAvailable line options:")
print("1. Simple line - Clean but no direction indicator")
print("2. Size difference - Small circle (origin) → Large circle (destination)")
print("3. Triangle arrow head - Custom triangle shape at destination")
print("4. Triangle marker with angle - Uses Plotly's triangle symbol")
print("5. Gradient markers - Growing circle size shows direction")
print("6. Multiple arrow symbols - Arrows placed along the line\n")

fig.show()
