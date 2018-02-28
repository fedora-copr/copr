$(document).ready(function(){
    $("#stats-link").removeClass("hidden");
    $("#graphs").removeClass("hidden");
    $(window).trigger('resize');
});

function graphConfig() {
    var colorPattern = ['#0088ce', '#cc0000', '#3f9c35', '#f5c12e', '#703fec',
                        '#003d44', '#35caed', '#ec7a08', '#470000', '#92d400'];
    var chart = {
        axis: {
            x: {
                type: 'timeseries'
            },
            y: {
                min: 0,
                padding: {bottom: 0}
            }
        },
        color: {pattern: colorPattern},
        data: {
            hide: ['average'],
            types: {
                'average': 'line',
                'tasks': 'area'
            },
            x: 'time',
            xFormat: '%Y-%m-%d %H:%M:%S'
        },
        grid: {
            y: {show: true}
        },
        point: {r: 2.5},
        tooltip: {
            format: {
                title: function(d) {
                    var a = d.toString().substring(0, 25) + 'UTC';
                    return a;
                },
                value: function(value, ratio, id) {
                    if (id === 'average') return value.toFixed(2);
                    else return value;
                }
            }
        },
        zoom: {enabled: true}
    };
    return chart;
};

function lineGraph(data, ticks, bind, format) {
    chart = graphConfig();
    chart.axis.x.tick = {
        culling: {max: ticks},
        format: format
    };
    chart.bindto = bind;
    chart.color.pattern = ['#cc8844', '#0088ce'];
    chart.data.columns = data;
    var chartDay = c3.generate(chart);
};

function chrootGraph(data, bind) {
    chart = graphConfig();
    chart.axis.x = {show: false};
    chart.bindto =  bind;
    chart.data = {
        columns: data,
        type: 'bar'
    };
    chart.size = {height: 550,
                  width: 400};
    chart.tooltip = {
        format: {
            title: function (x) {return ''}
        },
        position: function (data, width, height, element) {
            return {top: 0, left: -150};
        }
    }
    chart.zoom = {enabled: false};
    var chrootsChart = c3.generate(chart);
};

function smallGraph(data, bind) {
    var c3ChartDefaults = $().c3ChartDefaults();
    var sparklineChartConfig = c3ChartDefaults.getDefaultSparklineConfig();
    sparklineChartConfig.bindto = bind;
    sparklineChartConfig.color = {pattern: ['#cc8844']}
    sparklineChartConfig.data = {
        columns: data,
        type: 'area'
    };
    var sparklineChart = c3.generate(sparklineChartConfig);
};
