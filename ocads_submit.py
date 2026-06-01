import dash_bootstrap_components as dbc

class MetadataSubmitButton(dbc.Button):
    """
    A modular submit button that tells the global callback exactly which
    complex types and form instances to harvest when clicked.
    """
    def __init__(self, instance_id, targets, label="Save Section", color="primary", className=None, **kwargs):
        """
        :param instance_id: The specific database/XML instance context (e.g., 'primary_submitter', 'cruise_101')
        :param targets: A list of string complex-types this button is responsible for (e.g., ['person_name', 'contact_info'])
        :param label: The text displayed on the button
        """
        # Serialize the list of targets so it can be safely stored inside the Dash ID dictionary
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