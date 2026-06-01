import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from utils import TEMP_XML_FILE, get_all_entities_from_xml

class PolymorphicVariableManager(html.Div):
    """
    A specialized interface manager that handles adding, editing, and displaying
    a mixed collection of polymorphic variables matching the OCADS choice matrix.
    """
    def __init__(self, instance_id="dataset_core", className=None, **kwargs):
        super().__init__(**kwargs)
        self.instance_id = instance_id

        # Master mapping of class strings to clear, scannable user options
        self.variable_options = [
            {"label": "📊 Basic / Non-Measured Column (e.g., Sample ID, Bottle No)", "value": "BasicVariable"},
            {"label": "🌊 Standard Observed In-Situ Metric (e.g., Salinity, Temperature)", "value": "StdObservedVariable"},
            {"label": "🧪 Dissolved Inorganic Carbon (DIC)", "value": "DicMeasured"},
            {"label": "🧪 Total Alkalinity (TA)", "value": "TaMeasured"},
            {"label": "🧪 pH Measurement Profile", "value": "PhMeasured"},
            {"label": "🎛️ Continuous CO2 Analytical Track", "value": "Co2ContinuousVariable"},
            {"label": "🎛️ Discrete CO2 Sample Profile", "value": "Co2DiscreteVariable"}
        ]

        # Fetch any pre-existing variables inside the temporary XML file to seed the grid
        try:
            # We will implement this specific collection reader in Step 3 below
            initial_rows = get_variables_from_xml(TEMP_XML_FILE)
        except Exception:
            initial_rows = []

        layout = [
            # Overview Grid Interface
            dag.AgGrid(
                id={'type': 'var-matrix-grid', 'instance': self.instance_id},
                columnDefs=[
                    {'headerName': 'File Column Header', 'field': 'column_name', 'width': 220, 'checkboxSelection': True},
                    {'headerName': 'Variable Type Class', 'field': 'type_class', 'width': 200},
                    {'headerName': 'Unit / Scale', 'field': 'units', 'flex': 1}
                ],
                rowData=initial_rows,
                dashGridOptions={"rowSelection": "single", "popupParent": {"className": "root"}},
                className="ag-theme-alpine mb-3"
            ),

            # Trigger to open the wizard modal
            dbc.Button(
                "➕ Add Variable to Dataset Matrix",
                id={'type': 'open-var-modal-btn', 'instance': self.instance_id},
                color="primary",
                size="sm",
                className="mb-4"
            ),

            # The Polymorphic Factory Modal Window Wrapper
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("Configure Dataset Variable Profile")),
                dbc.ModalBody([
                    html.Div([
                        html.Label("Select Variable Scientific Genesis Type:", className="fw-bold mb-2 small text-secondary"),
                        dcc.Dropdown(
                            id={'type': 'var-factory-dropdown', 'instance': self.instance_id},
                            options=self.variable_options,
                            placeholder="Choose matching parameter rules...",
                            className="mb-4"
                        ),
                        html.Hr(),
                        # 🎯 The dynamic form insertion target anchor zone
                        html.Div(id={'type': 'var-dynamic-form-container', 'instance': self.instance_id})
                    ])
                ]),
                dbc.ModalFooter([
                    dbc.Button("Cancel", id={'type': 'close-var-modal-btn', 'instance': self.instance_id}, color="light"),
                    dbc.Button("Commit Variable to Pool", id={'type': 'save-var-matrix-btn', 'instance': self.instance_id}, color="success")
                ])
            ], id={'type': 'var-matrix-modal', 'instance': self.instance_id}, is_open=False, size="xl")
        ]

        default_class = 'p-4 border rounded bg-white shadow-sm'
        self.className = f'{default_class} {className}' if className else default_class
        self.children = layout