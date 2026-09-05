import { Component, type ErrorInfo, type ReactNode } from "react";
import { ChartFrame } from "@/design-system";

interface Props {
  title: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/** A render error inside one widget shows that widget's error state and
 * leaves the rest of the dashboard standing. Retry remounts the child. */
export class WidgetBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`Dashboard widget "${this.props.title}" failed`, error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <ChartFrame title={this.props.title} error={this.state.error} onRetry={() => this.setState({ error: null })}>
          {null}
        </ChartFrame>
      );
    }
    return this.props.children;
  }
}
