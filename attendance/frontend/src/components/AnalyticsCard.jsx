import React from 'react';
import './AnalyticsCard.css';

const AnalyticsCard = ({ title, value, subtitle, icon, trend, trendValue, color = 'blue' }) => {
    const trendIcon = trend === 'up' ? '↗' : trend === 'down' ? '↘' : '→';
    const trendColor = trend === 'up' ? '#22c55e' : trend === 'down' ? '#ef4444' : '#64748b';

    return (
        <div className={`analytics-card analytics-card-${color}`}>
            <div className="analytics-card-header">
                <div className="analytics-card-icon">{icon}</div>
                <div className="analytics-card-title">{title}</div>
            </div>
            <div className="analytics-card-value">{value}</div>
            {subtitle && <div className="analytics-card-subtitle">{subtitle}</div>}
            {trend && (
                <div className="analytics-card-trend" style={{ color: trendColor }}>
                    <span className="trend-icon">{trendIcon}</span>
                    <span className="trend-value">{trendValue}</span>
                </div>
            )}
        </div>
    );
};

export default AnalyticsCard;
