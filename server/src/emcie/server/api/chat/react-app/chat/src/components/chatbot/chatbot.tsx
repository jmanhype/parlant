import { ReactElement, useState } from "react";
import Sessions from "../sessions/sessions";
import SessionEvents from "../events/events";

export default function Chatbot(): ReactElement {
    const [sessionId, setSessionId] = useState(null);
    return (
        <div className="main bg-slate-200 flex justify-center items-center h-screen">
            <div className="flex justify-between items-center w-4/5 h-[80%] border border-gray-800 border-solid rounded-lg">
                <div className="flex-1 h-full pb-4 border-r border-r-gray-900 border-solid">
                    <Sessions sessionId={sessionId} setSession={setSessionId}/>
                </div>
                <div className="flex-[2] h-full">
                    {sessionId && <SessionEvents sessionId={sessionId}/>}
                </div>
            </div>
        </div>
    )
}