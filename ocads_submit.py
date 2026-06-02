import dash_bootstrap_components as dbc

class MetadataSubmitButton(dbc.Button):
    """
    A modular submit button that tells the global callback exactly which
    absolute XPath branches and form instances to harvest when clicked.
    """
    def __init__(self, instance_id, targets, label="Save Section", color="primary", className=None, **kwargs):
        """
        :param instance_id: The specific operational instance context (e.g., 'doc_root', 'cruise_variables')
        :param targets: A list of absolute XPath prefix strings this button sweeps up
                        (e.g., ['dataset_metadata/document_metadata', 'dataset_metadata/dataset_base_fields'])
        :param label: The text displayed on the button surface
        """
        # Serialize the list of target paths so they can be safely stored inside the Dash ID dictionary
        serialized_targets = ",".join(targets)

        button_id = {
            'type': 'metadata-submit',
            'instance': instance_id,
            'targets': serialized_targets
        }

        default_class = "mt-3 w-100"
        combined_class = f"{default_class} {className}" if className else default_class

        super().__init__(
            children=label,
            id=button_id,
            color=color,
            className=combined_class,
            n_clicks=0,
            **kwargs
        )