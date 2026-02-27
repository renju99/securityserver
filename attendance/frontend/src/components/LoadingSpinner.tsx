import React from 'react';
import './LoadingSpinner.css';

export const LoadingSpinner = ({ size = 'medium', text = '' }) => {
    const sizeClass = `spinner-${size}`;

    return (
        <div className="loading-spinner-container">
            <div className={`loading-spinner ${sizeClass}`}>
                <div className="spinner-ring"></div>
                <div className="spinner-ring"></div>
                <div className="spinner-ring"></div>
            </div>
            {text && <p className="loading-text">{text}</p>}
        </div>
    );
};

export const TableSkeleton = ({ rows = 5, columns = 6 }) => {
    return (
        <div className="skeleton-table">
            <div className="skeleton-table-header">
                {[...Array(columns)].map((_, i) => (
                    <div key={i} className="skeleton-cell skeleton-shimmer"></div>
                ))}
            </div>
            {[...Array(rows)].map((_, rowIndex) => (
                <div key={rowIndex} className="skeleton-table-row">
                    {[...Array(columns)].map((_, colIndex) => (
                        <div key={colIndex} className="skeleton-cell skeleton-shimmer"></div>
                    ))}
                </div>
            ))}
        </div>
    );
};

export const CardSkeleton = () => {
    return (
        <div className="skeleton-card">
            <div className="skeleton-header skeleton-shimmer"></div>
            <div className="skeleton-text skeleton-shimmer"></div>
            <div className="skeleton-text skeleton-shimmer" style={{ width: '80%' }}></div>
            <div className="skeleton-text skeleton-shimmer" style={{ width: '60%' }}></div>
        </div>
    );
};
