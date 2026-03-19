from datetime import datetime, timedelta, timezone
import spiceypy as sp
import numpy as np
from scipy.spatial.transform import Rotation as R
import plotly.graph_objects as go
from demosat_data_utils.ephemeris import EphemerisContainer
from demosat_data_utils.ground_stations import GroundStationContainer
import ipywidgets as widgets
from IPython.display import display
import tts_spice.furnish
import tts_dtat.plot as dtatplot
from copy import deepcopy
from tts_html_utils.jupyter.grid import IPythonGrid
import pandas as pd

tts_spice.furnish.leap_seconds()
tts_spice.furnish.planetary_ephemerides()
tts_spice.furnish.planetary_constants()
tts_spice.furnish.rotation_kernels('earth')

class SyncedPlot:
    def __init__(self, channels, dataframe):
        """
        Initialize a synchronized plot that updates with the slider.
        
        Args:
            channels: List of channel names to plot
            data_container: Data container with a between() method
        """
        self.channels = channels
        self.dataframe = dataframe
        self.begin_time = None
        self.end_time = None
        self.fig_widget = None
        
    def create_widget(self, begin_time, end_time):
        """
        Create the initial plot widget.
        
        Args:
            begin_time: Start time for data display
            end_time: End time for data display
        
        Returns:
            A FigureWidget for display
        """
        self.begin_time = begin_time
        self.end_time = end_time
        
        # Create the initial plot
        #TO DO: Make this be with data containers instead
        filtered_data = self.dataframe[self.dataframe['scet'] >= begin_time]
        filtered_data = filtered_data[filtered_data['scet'] <= end_time]
        
        # Create event for the center time (midpoint between begin and end)
        center_time = begin_time + (end_time - begin_time) / 2
        events = {}
        
        # Handle the case where self.channels is a nested list structure
        # dtat expects events keyed by individual channel names (strings), not tuples
        for i, channel_group in enumerate(self.channels):
            if isinstance(channel_group, list):
                # Add event to each channel in the first subplot
                for channel_name in channel_group:
                    if i == 0:
                        # Pass datetime object directly - dtat now handles both datetime and string
                        events[channel_name] = [(center_time, "Current Time", f"Current Time: {center_time.strftime('%Y-%m-%d %H:%M:%S')}")]
                    else:
                        events[channel_name] = []
            else:
                # Single channel (not a list)
                if i == 0:
                    events[channel_group] = [(center_time, "Current Time", f"Current Time: {center_time.strftime('%Y-%m-%d %H:%M:%S')}")]
                else:
                    events[channel_group] = []

        dtatfig, c, m, t = dtatplot.make_stacked_graph(
            filtered_data,
            y_vars=self.channels,
            doy=True,
            events=events,
            event_line=True  # Add vertical line for events
        )
        
        # Ensure the x-axis is set to date type with proper formatting
        dtatfig.layout.xaxis.type = 'date'
        dtatfig.layout.xaxis.tickformat = '%Y-%m-%d %H:%M:%S'
        
        # Explicitly set the x-axis range to match the data
        # Convert datetime objects to strings in ISO format for Plotly
        range_start = begin_time.isoformat()
        range_end = end_time.isoformat()
        dtatfig.layout.xaxis.range = [range_start, range_end]
        
        # Create the widget with zero margins
        self.fig_widget = go.FigureWidget(dtatfig)
        
        # Set layout properties to minimize spacing and ensure responsive sizing
        self.fig_widget.layout.margin = dict(l=0, r=0, t=0, b=0, pad=0)
        self.fig_widget.layout.autosize = True
        self.fig_widget.layout.width = None  # Remove any fixed width to allow container sizing
        
        return self.fig_widget


    def update(self, begin_time, end_time):
        """
        Update the plot with new time range.
        
        Args:
            begin_time: New start time for data display
            end_time: New end time for data display
        """
        if self.fig_widget is None:
            return
            
        self.begin_time = begin_time
        self.end_time = end_time
        
        # Get new data for the time range
        filtered_data = self.dataframe[self.dataframe['scet'] >= begin_time]
        filtered_data = filtered_data[filtered_data['scet'] <= end_time]
        # Create a new figure with the updated data
        # Create event for the center time (midpoint between begin and end)
        center_time = begin_time + (end_time - begin_time) / 2
        events = {}
        
        # Handle the case where self.channels is a nested list structure
        # dtat expects events keyed by individual channel names (strings), not tuples
        for i, channel_group in enumerate(self.channels):
            if isinstance(channel_group, list):
                # Add event to each channel in the first subplot
                for channel_name in channel_group:
                    if i == 0:
                        # Pass datetime object directly - dtat now handles both datetime and string
                        events[channel_name] = [(center_time, "Current Time", f"Current Time: {center_time.strftime('%Y-%m-%d %H:%M:%S')}")]
                    else:
                        events[channel_name] = []
            else:
                # Single channel (not a list)
                if i == 0:
                    events[channel_group] = [(center_time, "Current Time", f"Current Time: {center_time.strftime('%Y-%m-%d %H:%M:%S')}")]
                else:
                    events[channel_group] = []
            
        dtatfig, c, m, t = dtatplot.make_stacked_graph(
            filtered_data,
            y_vars=self.channels,
            doy=True,
            events=events,
            event_line=True  # Add vertical line for events
        )
        
        with self.fig_widget.batch_update():
            # Update traces
            for i, trace in enumerate(dtatfig.data):
                if i < len(self.fig_widget.data):
                    self.fig_widget.data[i].x = pd.to_datetime(trace.x).to_pydatetime()
                    self.fig_widget.data[i].y = trace.y

            # Clear existing annotations AND shapes
            self.fig_widget.layout.annotations = []
            self.fig_widget.layout.shapes = []
            
            # Copy annotations from the new figure
            if hasattr(dtatfig.layout, 'annotations') and dtatfig.layout.annotations:
                self.fig_widget.layout.annotations = dtatfig.layout.annotations
            
            # Copy shapes (vertical lines) from the new figure
            if hasattr(dtatfig.layout, 'shapes') and dtatfig.layout.shapes:
                self.fig_widget.layout.shapes = dtatfig.layout.shapes
            
            # Always force the x-axis to be the full time range
            range_start = begin_time.isoformat()
            range_end = end_time.isoformat()
            self.fig_widget.layout.xaxis.range = [range_start, range_end]

class SyncedTable:
    def __init__(self, data_container, time_label, records_before, records_after):
        """
        Initialize a synchronized table that updates with the slider.
        
        Args:
            data_container: Data container with between() and power_table() methods
            time_label: Label for the time column
            records_before: Number of records to display before the current time
            records_after: Number of records to display after the current time
        """
        self.data_container = data_container
        self.begin_time = None
        self.end_time = None
        self.html_widget = None
        self.time_label = time_label
        self.records_before = records_before
        self.records_after = records_after
        
    def create_widget(self, current_time):
        """
        Create the initial table widget.
        
        Args:
            begin_time: Start time for data display
            end_time: End time for data display
            
        Returns:
            An HTML widget for display
        """
        self.current_time = current_time
        
        # Create the HTML widget with zero margins
        self.html_widget = widgets.HTML()
        
        # Set layout properties to minimize spacing
        self.html_widget.layout.margin = '0'
        self.html_widget.layout.padding = '0'
        self.html_widget.layout.border = 'none'
        self.html_widget.layout.box_sizing = 'border-box'
        
        # Update with initial data
        self.update(current_time)
        
        return self.html_widget
        
    def update(self, current_time):
        """
        Update the table with new time range.
        
        Args:
            current_time: Current time for data display
        """
        if self.html_widget is None:
            return
            
        self.current_time = current_time
        
        # Get filtered data and render the table
        records_before =  self.data_container.before(self.current_time, self.time_label)[-self.records_before:]
        current_time_record = deepcopy(records_before)
        current_time_record.records = [self.data_container[0]]
        for k, v in current_time_record[0].values.items():
            if k == self.time_label:
                current_time_record[0][k] = current_time
            else:
                current_time_record[0][k] = 'DISPLAY TIME'
        records_after = self.data_container.after(self.current_time, self.time_label)[:self.records_after]
        display_records = records_before + current_time_record + records_after
        row_styles = [r.default_html_row_style for r in records_before] + [{'background-color': 'lightblue'}] + [r.default_html_row_style for r in records_after]
        
        table_html = display_records.power_table(row_styles=row_styles).render()
        
        # Update the widget
        self.html_widget.value = table_html

class EarthMap:
    def __init__(self, epehmeris_csv_path):
        self.ephemeris = EphemerisContainer(csv_path='ephemeris.txt', cast_fields=True)
        
        # Use the first time in the ephemeris container
        if len(self.ephemeris) > 0:
            first_time = self.ephemeris[0].time
            self.utc_time = (first_time + timedelta(hours=3)).strftime("%Y-%m-%d T%H:%M:%S")
        else:
            # Fallback if ephemeris is empty
            self.utc_time = "2024-02-02 T20:00:00"
            
        self.plots = []
        self.tables = []
        self.grid = IPythonGrid()
        self.grid_layout = None

        # Initialize ground stations
        self.ground_stations = GroundStationContainer()
        
        self.update_time(datetime.strptime(self.utc_time, "%Y-%m-%d T%H:%M:%S"))
    
    def add_plot(self, channels, data_container, name=None):
        """
        Add a synchronized plot to the Earth map.
        
        Args:
            channels: List of channel names to plot
            data_container: Data container with a between() method
            name: Optional name for the plot to use in layout configuration.
                  If None, will use 'plot_N' where N is the index of the plot.
            
        Returns:
            The added SyncedPlot instance
        """
        plot = SyncedPlot(channels, data_container)
        plot_index = len(self.plots)
        plot_name = name if name is not None else f'plot_{plot_index}'
        plot.name = plot_name
        self.plots.append(plot)
        return plot

    def add_table(self, data_container, time_label, records_before, records_after, name=None): 
        """
        Add a synchronized table to the Earth map.
        
        Args:
            data_container: Data container with before(), after() and power_table() methods
            time_label: Label for the time column
            records_before: Number of records to display before the current time
            records_after: Number of records to display after the current time
            name: Optional name for the table to use in layout configuration.
                  If None, will use 'table_N' where N is the index of the table.
            
        Returns:
            The added SyncedTable instance
        """
        table = SyncedTable(data_container, time_label, records_before, records_after)
        table_index = len(self.tables)
        table_name = name if name is not None else f'table_{table_index}'
        table.name = table_name
        self.tables.append(table)
        return table
        
    def configure_grid(self, layout=None):
        """
        Configure the grid layout for displaying the map, plots, and tables.
        
        Args:
            layout: List of rows, where each row is a list of cell configurations.
                   Each cell configuration is a list specifying [key, height, width].
                   If None, a default layout will be created with all components stacked vertically.
                   
        Example:
            earth_map.configure_grid([
                [['map', '400px', '100%']],
                [['plot_0', '300px', '50%'], ['plot_1', '300px', '50%']],
                [['table_0', '300px', '100%']]
            ])
            
        Returns:
            self for method chaining
        """
        self.grid_layout = layout
        return self
        
    def _validate_layout_config(self, rows):
        """
        Validate and fix layout configuration issues.
        
        Args:
            rows: List of row configurations
            
        Returns:
            Fixed rows configuration
        """
        fixed_rows = []
        
        for row in rows:
            # Ensure row has minimum height
            if 'height' in row and row['height'].endswith('px'):
                height_val = int(row['height'].replace('px', ''))
                if height_val < 50:  # Minimum reasonable height
                    row['height'] = '50px'
            
            # Check if cell widths add up to more than 100%
            if 'cells' in row:
                # For single-cell rows, ensure it spans 100%
                if len(row['cells']) == 1:
                    row['cells'][0]['width'] = '100%'
                else:
                    total_width = 0
                    specified_widths = 0
                    for cell in row['cells']:
                        if 'width' in cell and isinstance(cell['width'], str) and cell['width'].endswith('%'):
                            width_val = float(cell['width'].replace('%', ''))
                            total_width += width_val
                            specified_widths += 1
                    
                    # If total width exceeds 100%, scale down proportionally
                    if total_width > 100 and specified_widths > 0:
                        scale_factor = 100 / total_width
                        for cell in row['cells']:
                            if 'width' in cell and isinstance(cell['width'], str) and cell['width'].endswith('%'):
                                width_val = float(cell['width'].replace('%', ''))
                                cell['width'] = f"{width_val * scale_factor:.1f}%"
                    
                    # If total width is less than 100%, distribute remaining space
                    elif total_width < 100 and specified_widths > 0:
                        remaining_width = 100 - total_width
                        # Add the remaining width to the last cell with a specified width
                        for cell in reversed(row['cells']):
                            if 'width' in cell and isinstance(cell['width'], str) and cell['width'].endswith('%'):
                                width_val = float(cell['width'].replace('%', ''))
                                cell['width'] = f"{width_val + remaining_width:.1f}%"
                                break
            
            fixed_rows.append(row)
        
        return fixed_rows
            
    def cartesian_to_spherical(self, v):
        x, y, z = v
        r = np.sqrt(x**2 + y**2 + z**2)
        theta = np.arccos(z / r)          # polar angle from z-axis
        phi = np.arctan2(y, x)            # azimuth from x-axis
        return r, theta, phi
    
    def cartesian_to_latlon(self, v):
        r, phi, theta = self.cartesian_to_spherical(v)
        lat = (np.pi/2 - phi)/np.pi*180
        lon = theta/np.pi*180
        return lat, lon
    
    def calulate_terminator_lat_lon(self, earth_to_sun_vector):
        theta = np.arange(12)
        x = np.cos(theta)
        y = np.sin(theta)
        z = np.zeros(len(theta))
        v = np.vstack([x,y,z]).T
    
        v1 = np.array([0, 0, 1])   # original vector
        v2 = earth_to_sun_vector
        v2 = v2/np.linalg.norm(v2)
    
        # Compute rotation vector (axis-angle)
        axis = np.cross(v1, v2)
        axis /= np.linalg.norm(axis)
        angle = np.arccos(np.dot(v1, v2))
    
        if angle == 0:
            rotation = R.identity()
        else:
            rotvec = axis * angle
            rotation = R.from_rotvec(rotvec)
    
        # Rotation matrix
        if all(v1 == v2):
            R_mat = np.identity(3)
        else:
            R_mat = rotation.as_matrix()
    
        # Apply it
        rotated_v1 = rotation.apply(v1)
        lat, lon = self.cartesian_to_latlon(rotation.apply(v).T)
        lat = [l for l in lat][:-1]
        lon = [l for l in lon][:-1]
    
        return lat, lon

    def plot(self):
        fig = go.FigureWidget()

        fig.layout.width = 1100
        
        fig.update_geos(
            resolution=110,
            showland=True, landcolor="LightGreen",
            showocean=True, oceancolor="LightBlue",
            showlakes=False
        )
        
        # translucent rectangle using lon/lat
        fig.add_trace(go.Scattergeo(
            lat=self.shadow_lat,
            lon=self.shadow_lon,
            fill="toself",
            fillcolor="rgba(0, 0, 0, 0.4)",
            mode="lines",
            line=dict(width=0),
            hoverinfo="skip",
            name="Surface in Shadow"
        ))
        
        fig.add_trace(go.Scattergeo(
            lat=self.ephem_lat,
            lon=self.ephem_lon,
            mode="lines",
            line=dict(color="blue", width=3),
            name="Orbit Track"
        ))
        
        fig.add_trace(go.Scattergeo(
            lat=[self.subsolar_lat],
            lon=[self.subsolar_lon],
            mode="markers",
            marker=dict(
                size=15,
                color="yellow"
            ),        
            name="Subsolar Point"
        ))
        
        fig.add_trace(go.Scattergeo(
            lat=[self.sc_lat],
            lon=[self.sc_lon],
            mode="markers",
            marker=dict(
                size=15,
                color="red"
            ),        
            name="Spacecraft"
        ))
        
        # Add ground stations with tooltips
        gs_lats = []
        gs_lons = []
        gs_names = []
        gs_hover_texts = []
        
        for station in self.ground_stations:
            gs_lats.append(station['Latitude'])
            # The ground station data appears to have inconsistent longitude conventions
            # Wallops: 75.47 should be -75.47 (West, not East)
            # McMurdo: 167.02 is correct (East)
            # Alaska: -147.85 is correct (West)
            lon = station['Longitude']
            
            # Check the station name to apply specific fixes
            if station['Name'] == 'Wallops Test Range':
                # Wallops is actually in the western hemisphere (negative longitude)
                adjusted_lon = -lon
            else:
                # For other stations, use the longitude as is
                adjusted_lon = lon
            
            gs_lons.append(adjusted_lon)
            gs_names.append(station['Name'])
            gs_hover_texts.append(
                f"Name: {station['Name']} ({station['Abbreviation']})<br>"
                f"Latitude: {station['Latitude']:.2f}°<br>"
                f"Longitude: {station['Longitude']:.2f}°<br>"
                f"Altitude: {station['Altitude']:.3f} km"
            )
        
        fig.add_trace(go.Scattergeo(
            lat=gs_lats,
            lon=gs_lons,
            mode="markers+text",
            marker=dict(
                size=12,
                color="black",
                symbol="x"
            ),
            text=gs_names,
            textposition="top center",
            hoverinfo="text",
            hovertext=gs_hover_texts,
            name="Ground Stations"
        ))
        
        fig.update_layout(
            height=500,
            margin=dict(r=0, t=0, l=0, b=0)
        )
        
        self.fig = fig
        return fig

    def update_time(self, utc_datetime):
        self.utc_datetime = utc_datetime
        self.utc_time = utc_datetime.strftime("%Y-%m-%d T%H:%M:%S")
    
        self.et = sp.str2et(self.utc_time)
        self.state, self.light_time = sp.spkezr("SUN", self.et, "J2000", "NONE", "EARTH")
    
        self.pos_vector = self.state[:3]
        self.unit_vector = self.pos_vector / np.linalg.norm(self.pos_vector)
    
        self.rotation_matrix = sp.pxform("J2000", "ITRF93", self.et)
        self.pos_earth_fixed = self.rotation_matrix @ self.pos_vector
    
        self.shadow_lat, self.shadow_lon = self.calulate_terminator_lat_lon(self.pos_earth_fixed)
        self.subsolar_lat, self.subsolar_lon = self.cartesian_to_latlon(self.pos_earth_fixed)
    
        this_orbit = self.ephemeris.between('Time', utc_datetime - timedelta(minutes=50), utc_datetime + timedelta(minutes=50))
        current_position = self.ephemeris.before(utc_datetime)[-1]
        self.sc_lat, self.sc_lon = current_position.lat_lon

        lat_lon = [v.lat_lon for v in this_orbit]
        self.ephem_lat = [ll[0] for ll in lat_lon]
        self.ephem_lon = [ll[1] for ll in lat_lon]
    
    def update_plot(self):
        """
        Update the Earth map plot and all synchronized plots and tables.
        """
        # Update the Earth map
        with self.fig.batch_update():
            self.fig.data[0].lat = self.shadow_lat
            self.fig.data[0].lon = self.shadow_lon
    
            self.fig.data[1].lat = self.ephem_lat
            self.fig.data[1].lon = self.ephem_lon
            self.fig.data[1].mode = "lines"
    
            self.fig.data[2].lat = [self.subsolar_lat]
            self.fig.data[2].lon = [self.subsolar_lon]
            self.fig.data[2].mode = "markers"

            self.fig.data[3].lat = [self.sc_lat]
            self.fig.data[3].lon = [self.sc_lon]
            self.fig.data[3].mode = "markers"
        
        # Update all synchronized plots
        begin_time = datetime.strptime(self.plot_begin_time_string, "%Y-%jT%H:%M:%S")
        end_time = datetime.strptime(self.plot_end_time_string, "%Y-%jT%H:%M:%S")
        
        # Update all plots
        for plot in self.plots:
            plot.update(begin_time, end_time)
            
        # Update all synchronized tables with the current time
        current_time = datetime.strptime(self.utc_time, "%Y-%m-%d T%H:%M:%S")
        
        # Update all tables
        for table in self.tables:
            table.update(current_time)

    def on_slider_change(self, change):
        new_time = self.base_time + timedelta(minutes=change['new'])
        self.plot_begin_time_string = (new_time - timedelta(minutes=50)).strftime("%Y-%jT%H:%M:%S")
        self.plot_end_time_string = (new_time + timedelta(minutes=50)).strftime("%Y-%jT%H:%M:%S")
        new_time_str = new_time.strftime("%Y-%jT%H:%M:%S")
        self.utc_time = new_time.strftime("%Y-%m-%d T%H:%M:%S")
        self.time_labels.value = f'First Displayed Time: {self.plot_begin_time_string}<br>Displayed Spacecraft Time: {new_time_str}<br>Last Displayed Time: {self.plot_end_time_string}'
        self.update_time(new_time)
        self.update_plot()

    def configure_layout(self, layout):
        """
        Configure the grid layout for displaying the map, plots, and tables.
        
        Args:
            layout: List of rows, where each row is a list of cell configurations.
                   Each cell configuration is a list specifying [key, height, width].
                   
        Example:
            earth_map.configure_layout([
                [['controls', '80px', '100%']],
                [['map', '400px', '100%']],
                [['plot_0', '300px', '50%'], ['plot_1', '300px', '50%']],
                [['table_0', '300px', '100%']]
            ])
            
        Returns:
            self for method chaining
        """
        self.grid_layout = layout
        return self
        
    def display(self, return_html=False):
        """
        Create and display the Earth map with synchronized plots and tables using IPythonGrid.
        
        Args:
            return_html: If True, return an IPython.display.HTML object. If False, return the grid object.
        
        Returns:
            Either an HTML object (if return_html=True) or the IPythonGrid object (if return_html=False).
        """
        # Create the Earth map plot if not already created
        if not hasattr(self, 'fig'):
            self.plot()
        
        # Calculate the time range from ephemeris to set slider bounds
        if len(self.ephemeris) > 0:
            first_ephem_time = self.ephemeris[0].time
            last_ephem_time = self.ephemeris[-1].time
            
            # Set base time to the middle of the ephemeris range
            middle_time = first_ephem_time + (last_ephem_time - first_ephem_time) / 2
            self.base_time = middle_time
            self.utc_time = middle_time.strftime("%Y-%m-%d T%H:%M:%S")
            
            # Calculate slider range in minutes from the middle
            min_offset_minutes = int((first_ephem_time - middle_time).total_seconds() / 60)
            max_offset_minutes = int((last_ephem_time - middle_time).total_seconds() / 60)
        else:
            # Fallback if ephemeris is empty
            self.base_time = datetime.strptime(self.utc_time, "%Y-%m-%d T%H:%M:%S")
            min_offset_minutes = -720
            max_offset_minutes = 720
        
        # Define the slider: minutes offset from middle time
        self.slider = widgets.IntSlider(
            value=0,
            min=min_offset_minutes,
            max=max_offset_minutes,
            step=1,
            description='Minutes:',
            continuous_update=True,
            layout=widgets.Layout(width='100%')
        )
        
        # Set up time range for plots and tables
        time_string = self.base_time.strftime("%Y-%m-%d %H:%M:%S")
        self.plot_begin_time_string = (self.base_time - timedelta(minutes=50)).strftime("%Y-%jT%H:%M:%S")
        self.plot_end_time_string = (self.base_time + timedelta(minutes=50)).strftime("%Y-%jT%H:%M:%S")
        
        # Create time labels
        self.time_labels = widgets.HTML(value=f'First Displayed Time: {self.plot_begin_time_string}<br>Displayed Spacecraft Time: {time_string}<br>Last Displayed Time: {self.plot_end_time_string}')
        
        # Create plot widgets
        begin_time = datetime.strptime(self.plot_begin_time_string, "%Y-%jT%H:%M:%S")
        end_time = datetime.strptime(self.plot_end_time_string, "%Y-%jT%H:%M:%S")
        
        for plot in self.plots:
            plot_widget = plot.create_widget(begin_time, end_time)
            self.grid.add_content(plot.name, plot_widget)
            
        # Create table widgets
        for table in self.tables:
            table_widget = table.create_widget(self.base_time)
            self.grid.add_content(table.name, table_widget)
        
        # Set up slider observer
        self.slider.observe(self.on_slider_change, names='value')
        
        # Create controls with full width
        controls = widgets.VBox(
            [self.time_labels, self.slider],
            layout=widgets.Layout(width='100%')
        )
        
        # Add the map and controls to the grid
        self.grid.add_content('map', self.fig)
        self.grid.add_content('controls', controls)
        
        # Configure the layout if specified
        if self.grid_layout is not None:
            self.grid.configure_layout(self.grid_layout)
        else:
            # Create a default layout with all components stacked vertically
            default_layout = []
            
            # Add controls at the top
            default_layout.append([['controls', '80px', '100%']])
            
            # Add map
            default_layout.append([['map', '400px', '100%']])
            
            # Add plots
            for plot in self.plots:
                default_layout.append([[plot.name, '300px', '100%']])
            
            # Add tables
            for table in self.tables:
                default_layout.append([[table.name, '300px', '100%']])
            
            self.grid.configure_layout(default_layout)
        
        # Set default dimensions for all plots
        # This helps ensure they fit their containers
        self.grid.set_default_plot_dimensions(height=300)
        
        # Trigger an initial update to ensure plots are properly sized
        self.on_slider_change({'new': 1})
        self.on_slider_change({'new': 0})
        
        return self.grid.display()