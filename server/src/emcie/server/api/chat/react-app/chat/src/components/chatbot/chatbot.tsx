import { ReactElement, useState } from "react";
import SessionControl from "../session-control/session-control";
import Chat from "../chat/chat";

export default function Chatbot(): ReactElement {
    const [sessionId, setSessionId] = useState<string | null>(null);
    return (
        <div className="main bg-slate-200 flex justify-center items-center h-screen">
            <div className="flex justify-between max-w-[1500px] items-center w-4/5 h-[80%] border border-gray-800 border-solid rounded-lg flex-col lg:flex-row">
                <div className="h-2/5 lg:h-full pb-4 border-b border-b-gray-900 border-solid w-full lg:border-r-gray-900 lg:border-b-[transparent] lg:w-[30%] lg:border-r">
                    <SessionControl sessionId={sessionId} setSession={setSessionId}/>
                </div>
                <div className="h-3/5 w-full lg:w-[70%] lg:h-full">
                    {sessionId && <Chat sessionId={sessionId}/>}
                </div>
            </div>
        </div>
    )
}