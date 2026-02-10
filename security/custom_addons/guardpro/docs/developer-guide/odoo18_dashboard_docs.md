# Odoo 18 Dashboard Module - Complete Technical Documentation

## Table of Contents
1. [Overview](#overview)
2. [Core Dashboard Features](#core-dashboard-features)
3. [Technical Architecture](#technical-architecture)
4. [Implementation Guide](#implementation-guide)
5. [Widget Types](#widget-types)
6. [Database Structure](#database-structure)
7. [JavaScript Components](#javascript-components)
8. [XML Views](#xml-views)
9. [Python Models](#python-models)
10. [Security & Access Rights](#security-access-rights)
11. [Best Practices](#best-practices)

---

## Overview

Odoo 18's dashboard system is built on a modular architecture that allows developers to create interactive, real-time data visualizations. The dashboard framework uses:
- **Backend**: Python models with computed fields
- **Frontend**: Owl.js framework (Odoo's reactive JavaScript framework)
- **Views**: Custom dashboard view type inheriting from base views
- **Widgets**: Reusable components for different data representations

---

## Core Dashboard Features

### 1. **Real-time Data Updates**
- Automatic refresh capabilities
- WebSocket support for live updates
- Configurable refresh intervals

### 2. **Widget Library**
- KPI cards (numeric indicators)
- Charts (line, bar, pie, doughnut, area)
- Tables and lists
- Progress bars and gauges
- Custom HTML widgets

### 3. **Responsive Layout**
- Grid-based layout system
- Drag-and-drop repositioning
- Responsive breakpoints for mobile/tablet
- Customizable widget sizes

### 4. **Interactive Features**
- Click-through actions to detailed views
- Filter and domain support
- Date range selectors
- Drill-down capabilities

### 5. **Personalization**
- User-specific dashboard layouts
- Save/load dashboard configurations
- Share dashboards across users/groups

---

## Technical Architecture

### Component Hierarchy
```
dashboard_view (root)
├── dashboard_controller (JS)
├── dashboard_model (JS)
├── dashboard_renderer (JS)
└── dashboard_widgets/
    ├── kpi_card
    ├── chart_widget
    ├── table_widget
    └── custom_widgets
```

### Data Flow
```
Python Model → JSON Data → JS Controller → Renderer → DOM
     ↓                          ↓
  @api.model              OWL Components
  compute methods         reactive state
```

---

## Implementation Guide

### Step 1: Define Python Model

```python
# models/dashboard.py
from odoo import models, fields, api
from odoo.tools import date_utils
import json

class CustomDashboard(models.Model):
    _name = 'custom.dashboard'
    _description = 'Custom Dashboard'

    name = fields.Char('Dashboard Name', required=True)
    user_id = fields.Many2one('res.users', 'User', default=lambda self: self.env.user)
    
    # Dashboard data computed fields
    dashboard_data = fields.Text(compute='_compute_dashboard_data')
    
    @api.depends('user_id')
    def _compute_dashboard_data(self):
        for record in self:
            record.dashboard_data = json.dumps({
                'kpis': self._get_kpi_data(),
                'charts': self._get_chart_data(),
                'tables': self._get_table_data(),
            })
    
    def _get_kpi_data(self):
        """Compute KPI values"""
        return [
            {
                'name': 'Total Sales',
                'value': self._compute_total_sales(),
                'previous_value': self._compute_previous_sales(),
                'icon': 'fa-dollar',
                'color': 'success',
                'action': 'action_view_sales'
            },
            # Add more KPIs
        ]
    
    def _get_chart_data(self):
        """Compute chart data"""
        return [
            {
                'type': 'line',
                'title': 'Monthly Revenue',
                'labels': self._get_month_labels(),
                'datasets': [{
                    'label': 'Revenue',
                    'data': self._get_revenue_data(),
                    'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                    'borderColor': 'rgba(75, 192, 192, 1)',
                }]
            }
        ]
    
    def _get_table_data(self):
        """Compute table data"""
        records = self.env['sale.order'].search([
            ('state', '=', 'sale')
        ], limit=10, order='date_order desc')
        
        return {
            'columns': ['Order', 'Customer', 'Date', 'Amount'],
            'rows': [[r.name, r.partner_id.name, r.date_order, r.amount_total] 
                     for r in records]
        }
    
    @api.model
    def get_dashboard_data(self, domain=None, context=None):
        """API method for fetching dashboard data"""
        self.ensure_one()
        return json.loads(self.dashboard_data)
    
    def action_view_sales(self):
        """Action method for drill-down"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Orders',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('state', '=', 'sale')],
        }
```

### Step 2: Create XML Views

```xml
<!-- views/dashboard_views.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Dashboard View Definition -->
    <record id="view_custom_dashboard" model="ir.ui.view">
        <field name="name">custom.dashboard.view</field>
        <field name="model">custom.dashboard</field>
        <field name="arch" type="xml">
            <dashboard>
                <field name="name" invisible="1"/>
                <field name="dashboard_data" invisible="1"/>
                
                <!-- KPI Section -->
                <group name="kpi_section" col="4">
                    <widget name="kpi_card" 
                            data_field="dashboard_data" 
                            data_path="kpis"
                            class="o_dashboard_kpi"/>
                </group>
                
                <!-- Charts Section -->
                <group name="charts_section" col="2">
                    <widget name="chart_widget" 
                            chart_type="line"
                            data_field="dashboard_data"
                            data_path="charts[0]"
                            class="o_dashboard_chart"/>
                    
                    <widget name="chart_widget" 
                            chart_type="bar"
                            data_field="dashboard_data"
                            data_path="charts[1]"
                            class="o_dashboard_chart"/>
                </group>
                
                <!-- Table Section -->
                <group name="table_section">
                    <widget name="table_widget"
                            data_field="dashboard_data"
                            data_path="tables"
                            class="o_dashboard_table"/>
                </group>
            </dashboard>
        </field>
    </record>
    
    <!-- Action -->
    <record id="action_custom_dashboard" model="ir.actions.act_window">
        <field name="name">My Dashboard</field>
        <field name="res_model">custom.dashboard</field>
        <field name="view_mode">dashboard</field>
        <field name="target">main</field>
    </record>
    
    <!-- Menu Structure: Parent → Child -->
    <menuitem id="menu_dashboard_root"
              name="Dashboard"
              sequence="1"/>
    
    <menuitem id="menu_custom_dashboard"
              name="My Dashboard"
              parent="menu_dashboard_root"
              action="action_custom_dashboard"
              sequence="10"/>
</odoo>
```

### Step 3: JavaScript Dashboard Components

```javascript
/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Domain } from "@web/core/domain";

// KPI Card Widget
export class KPICardWidget extends Component {
    static template = "custom_module.KPICardWidget";
    static props = {
        data: Object,
        action: { type: Function, optional: true }
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
    }

    get variance() {
        const current = this.props.data.value;
        const previous = this.props.data.previous_value;
        if (!previous) return 0;
        return ((current - previous) / previous * 100).toFixed(2);
    }

    get varianceClass() {
        return this.variance >= 0 ? 'text-success' : 'text-danger';
    }

    async onCardClick() {
        if (this.props.data.action) {
            const action = await this.orm.call(
                'custom.dashboard',
                this.props.data.action,
                []
            );
            this.action.doAction(action);
        }
    }
}

// Chart Widget
export class ChartWidget extends Component {
    static template = "custom_module.ChartWidget";
    static props = {
        data: Object,
        type: { type: String, optional: true }
    };

    setup() {
        this.state = useState({
            chartInstance: null
        });
        
        onMounted(() => {
            this.renderChart();
        });
    }

    renderChart() {
        const ctx = this.chartRef.el;
        // Using Chart.js (include in assets)
        this.state.chartInstance = new Chart(ctx, {
            type: this.props.type || this.props.data.type,
            data: {
                labels: this.props.data.labels,
                datasets: this.props.data.datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: true,
                        text: this.props.data.title
                    }
                }
            }
        });
    }

    get chartRef() {
        return { el: this.__owl__.refs.chart };
    }
}

// Dashboard Controller
export class DashboardController extends Component {
    static template = "custom_module.DashboardView";
    static components = { KPICardWidget, ChartWidget };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            data: {},
            loading: true,
            selectedPeriod: 'month'
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                this.props.resModel,
                'get_dashboard_data',
                [this.props.resId],
                {
                    context: this.props.context
                }
            );
            this.state.data = data;
        } finally {
            this.state.loading = false;
        }
    }

    async onPeriodChange(period) {
        this.state.selectedPeriod = period;
        await this.loadDashboardData();
    }

    async onRefresh() {
        await this.loadDashboardData();
    }
}

// Register the view
registry.category("views").add("dashboard", {
    type: "dashboard",
    display_name: "Dashboard",
    icon: "fa fa-dashboard",
    multiRecord: false,
    Controller: DashboardController,
});
```

### Step 4: QWeb Templates

```xml
<!-- static/src/xml/dashboard_templates.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">

    <!-- Main Dashboard Template -->
    <t t-name="custom_module.DashboardView">
        <div class="o_dashboard_view">
            <!-- Header -->
            <div class="o_dashboard_header">
                <div class="o_dashboard_title">
                    <h2>Dashboard</h2>
                </div>
                <div class="o_dashboard_controls">
                    <select t-model="state.selectedPeriod" 
                            t-on-change="onPeriodChange">
                        <option value="day">Today</option>
                        <option value="week">This Week</option>
                        <option value="month">This Month</option>
                        <option value="year">This Year</option>
                    </select>
                    <button class="btn btn-secondary" t-on-click="onRefresh">
                        <i class="fa fa-refresh"/> Refresh
                    </button>
                </div>
            </div>

            <!-- Loading State -->
            <div t-if="state.loading" class="o_dashboard_loading">
                <i class="fa fa-spinner fa-spin fa-3x"/>
            </div>

            <!-- Dashboard Content -->
            <div t-else="" class="o_dashboard_content">
                <!-- KPIs Row -->
                <div class="o_dashboard_kpis row">
                    <t t-foreach="state.data.kpis" t-as="kpi" t-key="kpi_index">
                        <div class="col-md-3">
                            <KPICardWidget data="kpi"/>
                        </div>
                    </t>
                </div>

                <!-- Charts Row -->
                <div class="o_dashboard_charts row mt-4">
                    <t t-foreach="state.data.charts" t-as="chart" t-key="chart_index">
                        <div class="col-md-6">
                            <ChartWidget data="chart"/>
                        </div>
                    </t>
                </div>
            </div>
        </div>
    </t>

    <!-- KPI Card Template -->
    <t t-name="custom_module.KPICardWidget">
        <div class="o_kpi_card card" t-on-click="onCardClick">
            <div class="card-body">
                <div class="o_kpi_icon">
                    <i t-attf-class="fa {{props.data.icon}} fa-3x text-{{props.data.color}}"/>
                </div>
                <div class="o_kpi_content">
                    <div class="o_kpi_name text-muted">
                        <t t-esc="props.data.name"/>
                    </div>
                    <div class="o_kpi_value h2">
                        <t t-esc="props.data.value"/>
                    </div>
                    <div class="o_kpi_variance" t-att-class="varianceClass">
                        <i t-if="variance >= 0" class="fa fa-arrow-up"/>
                        <i t-else="" class="fa fa-arrow-down"/>
                        <t t-esc="Math.abs(variance)"/>%
                    </div>
                </div>
            </div>
        </div>
    </t>

    <!-- Chart Widget Template -->
    <t t-name="custom_module.ChartWidget">
        <div class="o_chart_widget card">
            <div class="card-header">
                <h5 t-esc="props.data.title"/>
            </div>
            <div class="card-body">
                <canvas t-ref="chart" height="300"/>
            </div>
        </div>
    </t>

</templates>
```

### Step 5: CSS Styling

```scss
/* static/src/scss/dashboard.scss */

.o_dashboard_view {
    padding: 20px;
    background-color: #f8f9fa;

    .o_dashboard_header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 30px;
        padding: 15px 20px;
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);

        .o_dashboard_title h2 {
            margin: 0;
            color: #2c3e50;
        }

        .o_dashboard_controls {
            display: flex;
            gap: 10px;

            select {
                padding: 8px 15px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        }
    }

    .o_dashboard_loading {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 400px;
    }

    .o_dashboard_kpis {
        margin-bottom: 30px;

        .o_kpi_card {
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            height: 100%;

            &:hover {
                transform: translateY(-5px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }

            .card-body {
                display: flex;
                align-items: center;
                gap: 20px;
                padding: 20px;
            }

            .o_kpi_icon {
                flex-shrink: 0;
            }

            .o_kpi_content {
                flex-grow: 1;

                .o_kpi_name {
                    font-size: 14px;
                    margin-bottom: 5px;
                }

                .o_kpi_value {
                    font-weight: bold;
                    margin: 10px 0;
                }

                .o_kpi_variance {
                    font-size: 14px;
                    font-weight: 600;
                }
            }
        }
    }

    .o_dashboard_charts {
        .o_chart_widget {
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);

            .card-header {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }

            .card-body {
                padding: 20px;
                min-height: 300px;
            }
        }
    }
}

// Responsive Design
@media (max-width: 768px) {
    .o_dashboard_kpis .col-md-3 {
        margin-bottom: 15px;
    }

    .o_dashboard_charts .col-md-6 {
        margin-bottom: 15px;
    }

    .o_dashboard_header {
        flex-direction: column;
        gap: 15px;

        .o_dashboard_controls {
            width: 100%;
            justify-content: space-between;
        }
    }
}
```

---

## Widget Types

### 1. KPI Cards
**Purpose**: Display single numeric metrics with comparison
**Data Structure**:
```python
{
    'name': 'Metric Name',
    'value': 1000,
    'previous_value': 800,
    'icon': 'fa-icon-name',
    'color': 'success|warning|danger|info',
    'action': 'method_name'  # optional click action
}
```

### 2. Charts
**Types**: line, bar, pie, doughnut, radar, polarArea
**Data Structure**:
```python
{
    'type': 'line',
    'title': 'Chart Title',
    'labels': ['Jan', 'Feb', 'Mar'],
    'datasets': [{
        'label': 'Dataset 1',
        'data': [10, 20, 30],
        'backgroundColor': 'color',
        'borderColor': 'color'
    }]
}
```

### 3. Tables
**Purpose**: Display tabular data with sorting/filtering
**Data Structure**:
```python
{
    'columns': ['Column1', 'Column2'],
    'rows': [['value1', 'value2'], ...],
    'actions': ['edit', 'delete']  # optional
}
```

### 4. Progress Indicators
**Purpose**: Show completion percentages
**Data Structure**:
```python
{
    'label': 'Task Completion',
    'value': 75,
    'max': 100,
    'color': 'success'
}
```

---

## Database Structure

### Models Required

```python
# models/__init__.py
from . import dashboard
from . import dashboard_widget
from . import dashboard_config

# models/dashboard_widget.py
class DashboardWidget(models.Model):
    _name = 'dashboard.widget'
    _description = 'Dashboard Widget'
    
    name = fields.Char('Widget Name', required=True)
    widget_type = fields.Selection([
        ('kpi', 'KPI Card'),
        ('chart', 'Chart'),
        ('table', 'Table'),
        ('gauge', 'Gauge'),
        ('custom', 'Custom')
    ], required=True)
    position_x = fields.Integer('Position X')
    position_y = fields.Integer('Position Y')
    width = fields.Integer('Width', default=4)
    height = fields.Integer('Height', default=4)
    config = fields.Text('Widget Configuration')  # JSON
    dashboard_id = fields.Many2one('custom.dashboard', 'Dashboard')

# models/dashboard_config.py
class DashboardConfig(models.Model):
    _name = 'dashboard.config'
    _description = 'Dashboard Configuration'
    
    name = fields.Char('Configuration Name')
    user_id = fields.Many2one('res.users', 'User')
    layout_config = fields.Text('Layout Configuration')  # JSON
    filters = fields.Text('Default Filters')  # JSON
```

---

## Security & Access Rights

```xml
<!-- security/ir.model.access.csv -->
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_custom_dashboard_user,custom.dashboard user,model_custom_dashboard,base.group_user,1,1,1,0
access_custom_dashboard_manager,custom.dashboard manager,model_custom_dashboard,base.group_system,1,1,1,1
access_dashboard_widget_user,dashboard.widget user,model_dashboard_widget,base.group_user,1,1,1,0

<!-- security/ir_rule.xml -->
<record id="dashboard_user_rule" model="ir.rule">
    <field name="name">Dashboard: User Access</field>
    <field name="model_id" ref="model_custom_dashboard"/>
    <field name="domain_force">[('user_id', '=', user.id)]</field>
    <field name="groups" eval="[(4, ref('base.group_user'))]"/>
</record>
```

---

## Best Practices

### 1. **Performance Optimization**
- Use `@api.depends` carefully to avoid unnecessary recomputation
- Implement caching for expensive queries
- Use database aggregation functions
- Limit data points in charts (max 50-100)
- Paginate table data

### 2. **Data Refresh Strategy**
```python
@api.model
def get_dashboard_data(self, refresh=False):
    cache_key = f'dashboard_data_{self.env.user.id}'
    if not refresh:
        cached = self.env['ir.cache'].get(cache_key)
        if cached:
            return cached
    
    data = self._compute_fresh_data()
    self.env['ir.cache'].set(cache_key, data, timeout=300)  # 5 min
    return data
```

### 3. **Error Handling**
```python
def _get_kpi_data(self):
    try:
        return self._compute_kpi()
    except Exception as e:
        _logger.error(f"Dashboard KPI error: {e}")
        return {'value': 0, 'error': True}
```

### 4. **Responsive Design**
- Use Bootstrap grid system
- Test on mobile devices
- Implement collapsible sections
- Use appropriate chart aspect ratios

### 5. **User Experience**
- Add loading indicators
- Implement error messages
- Provide export functionality
- Enable customization options
- Add tooltips for metrics

---

## Complete Module Structure

```
custom_dashboard/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── dashboard.py
│   ├── dashboard_widget.py
│   └── dashboard_config.py
├── views/
│   ├── dashboard_views.xml
│   ├── dashboard_templates.xml
│   └── assets.xml
├── static/
│   ├── src/
│   │   ├── js/
│   │   │   ├── dashboard_controller.js
│   │   │   ├── widgets/
│   │   │   │   ├── kpi_card.js
│   │   │   │   ├── chart_widget.js
│   │   │   │   └── table_widget.js
│   │   ├── xml/
│   │   │   └── dashboard_templates.xml
│   │   └── scss/
│   │       └── dashboard.scss
│   └── description/
│       └── icon.png
├── security/
│   ├── ir.model.access.csv
│   └── ir_rule.xml
└── data/
    └── dashboard_data.xml
```

### __manifest__.py
```python
{
    'name': 'Custom Dashboard',
    'version': '18.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Interactive Dashboard with KPIs and Charts',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/dashboard_views.xml',
        'data/dashboard_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_dashboard/static/src/js/**/*',
            'custom_dashboard/static/src/xml/**/*',
            'custom_dashboard/static/src/scss/**/*',
            ('include', 'web._assets_helpers'),
            'https://cdn.jsdelivr.net/npm/chart.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
```

---

## Prompt Template for Cursor AI

Use this template when prompting Cursor AI:

```
Create an Odoo 18 dashboard module with the following specifications:

MODULE NAME: [Your Module Name]
PURPOSE: [Dashboard Purpose]

REQUIREMENTS:
1. Python Models:
   - Create dashboard model with computed fields
   - Implement methods: [list specific KPIs, metrics]
   - Data sources: [models to query]

2. KPI Cards:
   - [KPI 1]: [description, calculation method]
   - [KPI 2]: [description, calculation method]
   - Include comparison with previous period
   - Add click-through actions

3. Charts:
   - [Chart 1]: [type, data source, labels]
   - [Chart 2]: [type, data source, labels]
   - Responsive and interactive

4. Tables:
   - Display: [data to show]
   - Columns: [column names]
   - Actions: [view, edit options]

5. Features:
   - Date range filtering
   - Auto-refresh every [X] seconds
   - Export to PDF/Excel
   - User-specific views

TECHNICAL REQUIREMENTS:
- Follow Odoo 18 OWL framework
- Use Chart.js for visualizations
- Implement proper security rules
- Responsive Bootstrap layout
- Error handling and loading states

MENU STRUCTURE:
- Create as a submenu under parent "Dashboard" menu
- Menu hierarchy: Dashboard (parent) → [Your Dashboard Name] (child)
- Set appropriate sequence for menu ordering

Follow the Odoo 18 dashboard architecture documented above.
```

---

This documentation provides everything needed to build production-ready dashboards in Odoo 18!