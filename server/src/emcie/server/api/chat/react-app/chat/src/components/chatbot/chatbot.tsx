import { createContext, Dispatch, ReactElement, SetStateAction, useContext, useState } from 'react';
import SessionControl from '../session-control/session-control';
import Chat from '../chat/chat';

interface SessionContext {
    setSessionId: Dispatch<SetStateAction<string | null>>;
    sessionId: string | null;
}

const SessionProvider = createContext<SessionContext>({sessionId: null, setSessionId: () => null});

// eslint-disable-next-line react-refresh/only-export-components
export const useSession = () => useContext(SessionProvider);

export default function Chatbot(): ReactElement {
    const [sessionId, setSessionId] = useState<string | null>(null);

    return (
        <SessionProvider.Provider value={{sessionId, setSessionId}}>
            <div data-testid="chatbot" className="main bg-slate-200 flex justify-center items-center h-screen">
                <div className="flex justify-between max-w-[1500px] items-center w-4/5 h-[80%] border border-gray-800 border-solid rounded-lg flex-col lg:flex-row">
                    <div className="h-2/5 lg:h-full pb-4 border-b border-b-gray-900 border-solid w-full lg:border-r-gray-900 lg:border-b-[transparent] lg:w-[30%] lg:border-r">
                        <SessionControl />
                    </div>
                    <div className="h-3/5 w-full lg:w-[70%] lg:h-full">
                        {sessionId && <Chat />}
                    </div>
                </div>
            </div>
        </SessionProvider.Provider>
    );
}