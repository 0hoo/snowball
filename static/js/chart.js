function showLineChartC3(bindto, columns, width, chart_type) {
    chart_type = chart_type || 'line';

    c3.generate({
        bindto: bindto,
        data: {
            x: 'date',
            columns: columns,
            type: chart_type
        },
        size: {
            width: width
        },
        padding: {
            right: 20
        },
        axis: {
            y: {
                tick: {
                    format: function (d) {
                        var df = Number( d3.format('.3f')(d) );
                        return df;
                    }
                }
            },
            x: {
                type : 'timeseries',
                tick: {
                    format: '%Y-%m-%d'
                }
            }
        }
    });
}

function showPieChartC3(bindto, columns, width) {
    c3.generate({
        bindto: bindto,
        data: {
            columns: columns,
            type : 'pie',
        }
    });
}