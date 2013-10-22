{% extends 'common_group.cpp' %}

{% if variables is defined %}
{% set _spikespace = variables['_spikespace'].arrayname %}
{% set _i = '_dynamic'+variables['_i'].arrayname %}
{% set _t = '_dynamic'+variables['_t'].arrayname %}
{% endif %}

{% block maincode %}
	//// MAIN CODE ////////////

	int _num_spikes = {{_spikespace}}[_num_{{_spikespace}}-1];
    if (_num_spikes > 0)
    {
        int _start_idx = 0;
        int _end_idx = - 1;
        for(int _i=0; _i<_num_spikes; _i++)
        {
            const int _idx = {{_spikespace}}[_i];
            if (_idx >= _source_start) {
                _start_idx = _i;
                break;
            }
        }
        for(int _i=_start_idx; _i<_num_spikes; _i++)
        {
            const int _idx = {{_spikespace}}[_i];
            if (_idx >= _source_stop) {
                _end_idx = _i;
                break;
            }
        }
        if (_end_idx == -1)
            _end_idx =_num_spikes;
        _num_spikes = _end_idx - _start_idx;
        if (_num_spikes > 0) {
        	for(int _i=_start_idx; _i<_end_idx; _i++)
        	{
        		const int _idx = {{_spikespace}}[_i];
        		{{_i}}.push_back(_idx-_source_start);
        		{{_t}}.push_back(t);
        	}
        }
    }
{% endblock %}

{% block extra_functions_cpp %}
void _write_{{codeobj_name}}()
{
	ofstream outfile;
	outfile.open("results/{{codeobj_name}}.txt", ios::out);
	if(outfile.is_open())
	{
		for(int s=0; s<{{_i}}.size(); s++)
		{
			outfile << {{_i}}[s] << ", " << {{_t}}[s] << endl;
		}
		outfile.close();
	} else
	{
		cout << "Error writing output file." << endl;
	}
}

void _debugmsg_{{codeobj_name}}()
{
	cout << "Number of spikes: " << {{_i}}.size() << endl;
}
{% endblock %}

{% block extra_functions_h %}
void _write_{{codeobj_name}}();
void _debugmsg_{{codeobj_name}}();
{% endblock %}

{% macro main_finalise() %}
_write_{{codeobj_name}}();
_debugmsg_{{codeobj_name}}();
{% endmacro %}
