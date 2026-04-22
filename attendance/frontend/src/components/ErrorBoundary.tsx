import React from 'react';

interface Props {
    children: React.ReactNode;
    label?: string;
}

interface State {
    error: Error | null;
    info: React.ErrorInfo | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
    state: State = { error: null, info: null };

    static getDerivedStateFromError(error: Error): Partial<State> {
        return { error };
    }

    componentDidCatch(error: Error, info: React.ErrorInfo) {
        console.error(`[ErrorBoundary${this.props.label ? ': ' + this.props.label : ''}]`, error, info);
        this.setState({ info });
    }

    reset = () => {
        this.setState({ error: null, info: null });
    };

    render() {
        if (this.state.error) {
            return (
                <div
                    style={{
                        padding: '1.5rem 2rem',
                        margin: '1rem',
                        background: '#fff5f5',
                        border: '1px solid #fecaca',
                        borderRadius: 12,
                        color: '#7f1d1d',
                        fontFamily: 'system-ui, -apple-system, sans-serif',
                    }}
                >
                    <h3 style={{ margin: '0 0 0.5rem', color: '#991b1b' }}>
                        Something went wrong{this.props.label ? ` in ${this.props.label}` : ''}.
                    </h3>
                    <p style={{ margin: '0 0 0.75rem' }}>
                        The rest of the app is still working. You can retry or switch to another tab.
                    </p>
                    <pre
                        style={{
                            background: '#fee2e2',
                            padding: '0.75rem',
                            borderRadius: 8,
                            fontSize: 12,
                            whiteSpace: 'pre-wrap',
                            maxHeight: 260,
                            overflow: 'auto',
                            margin: 0,
                        }}
                    >
                        {String(this.state.error?.message || this.state.error)}
                        {this.state.info?.componentStack ? `\n\n${this.state.info.componentStack}` : ''}
                    </pre>
                    <button
                        onClick={this.reset}
                        style={{
                            marginTop: '0.75rem',
                            background: '#dc2626',
                            color: '#fff',
                            border: 'none',
                            padding: '0.5rem 1rem',
                            borderRadius: 8,
                            cursor: 'pointer',
                            fontWeight: 600,
                        }}
                    >
                        Retry
                    </button>
                </div>
            );
        }
        return this.props.children as React.ReactElement;
    }
}

export default ErrorBoundary;
