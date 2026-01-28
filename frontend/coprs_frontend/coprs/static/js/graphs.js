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
            hide: ['avg running', 'success'],
            type: 'line',
            x: 'time',
            xFormat: '%Y-%m-%d %H:%M:%S'
        },
        grid: {
            y: {show: true}
        },
        point: {r: 2.5},
        tooltip: {
            format: {
                value: function(value, ratio, id) {
                    if (id === 'avg running') return value.toFixed(2);
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
    chart.color.pattern = ['#0088ce', '#cc8844', '#cc0000'];
    chart.data.columns = data;
    if (format === '%Y-%m-%d')
	chart.tooltip.format.title = function(d) {
	    var a = d.toString().substring(0, 15);
	    return a;
	}
    if (format === '%H:%M')
	chart.tooltip.format.title = function(d) {
	    var a = d.toString().substring(16, 25) + '(UTC)';
	    return a;
	}
    var chartDay = c3.generate(chart);
};

function chrootGraph(data, bind, options) {
    options = options || {};
    var limit = options.limit || data.length;
    var showAll = !!options.showAll;
    var paddingLeft = options.paddingLeft;
    // distro specific colors for chroot bars
    var osColors = { 'fedora': '#294172', 'centos': '#262f45', 'rhel': '#cc0000', 'epel': '#48759d', 'mageia': '#262f45',
                     'opensuse': '#73ba25', 'openmandriva': '#e06f00', 'amazon': '#f99d1c', 'alma': '#dadada', 'alien': '#333333' };
    var getColor = function(name) {
        if (!name) return osColors['alien'];
        var lowerName = name.toLowerCase();
        for (var os in osColors) {
            if (lowerName.indexOf(os) !== -1) return osColors[os];
        }
        return osColors['alien'];
    };
    var sorted = data.slice().sort(function(a, b) {
        return b[1] - a[1];
    });
    var visible = showAll ? sorted : sorted.slice(0, limit);
    var categories = [];
    var columns = ['Builds'];
    visible.forEach(function(item) {
        categories.push(item[0]);
        columns.push(item[1]);
    });
    var chart = {
        bindto: bind,
        size: {
            height: Math.max((categories.length * 25) + 50, 100)
        },
        padding: {
            left: paddingLeft
        },
        data: {
            columns: [columns],
            type: 'bar',
            color: function (color, d) {
                if (d.index !== undefined) return getColor(categories[d.index]);
                return color;
            },
            labels: true
        },
        axis: {
            rotated: true,
            x: {
                type: 'category',
                categories: categories,
                tick: {
                    multiline: false
                }
            },
            y: {
                show: false
            }
        },
        legend: {
            show: false
        },
        tooltip: {
            show: false
        },
        grid: {
            y: {show: false},
            x: {show: false}
        }
    };
    var chrootsChart = c3.generate(chart);
    return chrootsChart;
};

function chrootGraphWithToggle(data, bind, toggle, limit, options) {
    var showAll = false;
    var chart;
    var $toggle = toggle ? $(toggle) : null;
    options = options || {};

    function render() {
        if (chart) chart.destroy();
        chart = chrootGraph(data, bind, {
            limit: limit,
            showAll: showAll,
            paddingLeft: options.paddingLeft,
        });
        if ($toggle && $toggle.length) {
            if (data.length <= limit) {
                $toggle.hide();
            } else {
                $toggle.text(showAll ? "Show top " + limit : "Show full chart");
            }
        }
    }

    if (!data || data.length === 0) {
        if ($toggle && $toggle.length) $toggle.hide();
        return;
    }

    render();
    if ($toggle && $toggle.length) {
        $toggle.off("click").on("click", function(e) {
            e.preventDefault();
            showAll = !showAll;
            render();
        });
    }
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
