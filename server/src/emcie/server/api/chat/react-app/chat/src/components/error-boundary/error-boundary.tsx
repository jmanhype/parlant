import { Component, ReactNode } from 'react';

interface Props {
    children: ReactNode;
};

interface State {
    hasError: boolean;
    errorStack?: string;
}

export default class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = {hasError: false};
    }

    static getDerivedStateFromError() {
        return {hasError: true};
    }

    componentDidCatch(error: Error) {
        this.setState({errorStack: error.stack});
    }

    render(): ReactNode {
        return (
            this.state.hasError ?
            <div className='flex bg-main items-center justify-center h-screen flex-col'>
                <img src="/parlant-bubble-app-logo.svg" alt="Logo" height={200} width={200} className='mb-[10px]' />
                <h1 className='text-[20px]'>Oops! Something Went Wrong</h1>
                <p className='text-center'>We apologize for the inconvenience. Please try again later.</p>
                <div className={'flex justify-center max-h-[300px] mt-[40px] bg-[#f0eeee] rounded-[10px] p-[10px]  break-words border border-solid border-[#dedcdc]'}>
                    <code className='max-h-[300px] w-[600px] max-w-[80vw] overflow-auto'>
                        {this.state.errorStack}
                    </code>
                </div>
            </div> :
            this.props.children
        );
    }
}