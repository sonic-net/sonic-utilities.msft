import ast

QSFP_DATA_MAP = {
    'model': 'Vendor PN',
    'vendor_oui': 'Vendor OUI',
    'vendor_date': 'Vendor Date Code(YYYY-MM-DD Lot)',
    'manufacturer': 'Vendor Name',
    'vendor_rev': 'Vendor Rev',
    'serial': 'Vendor SN',
    'type': 'Identifier',
    'ext_identifier': 'Extended Identifier',
    'ext_rateselect_compliance': 'Extended RateSelect Compliance',
    'cable_length': 'cable_length',
    'cable_type': 'Length',
    'nominal_bit_rate': 'Nominal Bit Rate(100Mbs)',
    'specification_compliance': 'Specification compliance',
    'encoding': 'Encoding',
    'connector': 'Connector',
    'application_advertisement': 'Application Advertisement'
}

QSFP_CMIS_DELTA_DATA_MAP = {
    'host_lane_count': 'Host Lane Count',
    'media_lane_count': 'Media Lane Count',
    'active_apsel_hostlane1': 'Active application selected code assigned to host lane 1',
    'active_apsel_hostlane2': 'Active application selected code assigned to host lane 2',
    'active_apsel_hostlane3': 'Active application selected code assigned to host lane 3',
    'active_apsel_hostlane4': 'Active application selected code assigned to host lane 4',
    'active_apsel_hostlane5': 'Active application selected code assigned to host lane 5',
    'active_apsel_hostlane6': 'Active application selected code assigned to host lane 6',
    'active_apsel_hostlane7': 'Active application selected code assigned to host lane 7',
    'active_apsel_hostlane8': 'Active application selected code assigned to host lane 8',
    'media_interface_technology': 'Media Interface Technology',
    'hardware_rev': 'Module Hardware Rev',
    'cmis_rev': 'CMIS Rev',
    'active_firmware': 'Active Firmware',
    'inactive_firmware': 'Inactive Firmware',
    'supported_max_tx_power': 'Supported Max TX Power',
    'supported_min_tx_power': 'Supported Min TX Power',
    'supported_max_laser_freq': 'Supported Max Laser Frequency',
    'supported_min_laser_freq': 'Supported Min Laser Frequency'
}

CMIS_DATA_MAP = {**QSFP_DATA_MAP, **QSFP_CMIS_DELTA_DATA_MAP}

def covert_application_advertisement_to_output_string(indent, sfp_info_dict):
    key = 'application_advertisement'
    field_name = '{}{}: '.format(indent, QSFP_DATA_MAP[key])
    output = field_name
    try:
        app_adv_str = sfp_info_dict[key]
        app_adv_dict = ast.literal_eval(app_adv_str)
        if not app_adv_dict:
            output += 'N/A\n'
        else:
            lines = []
            for item in app_adv_dict.values():
                host_interface_id = item.get('host_electrical_interface_id')
                if not host_interface_id:
                    continue
                elements = []
                elements.append(host_interface_id)
                host_assign_options = item.get('host_lane_assignment_options')
                host_assign_options = hex(host_assign_options) if host_assign_options else 'Unknown'
                elements.append(f'Host Assign ({host_assign_options})')
                elements.append(item.get('module_media_interface_id', 'Unknown'))
                media_assign_options = item.get('media_lane_assignment_options')
                media_assign_options = hex(media_assign_options) if media_assign_options else 'Unknown'
                elements.append(f'Media Assign ({media_assign_options})')
                lines.append(' - '.join(elements))
            sep = '\n' + ' ' * len(field_name)
            output += sep.join(lines)
            output += '\n'
    except Exception:
        output += '{}\n'.format(app_adv_str)
    return output
