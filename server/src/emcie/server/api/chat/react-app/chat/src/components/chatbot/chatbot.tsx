import { ReactElement, useState } from "react";
import Sessions from "../sessions/sessions";
import SessionEvents from "../events/events";

export default function Chatbot(): ReactElement {
    const [sessionId, setSessionId] = useState(null);
    return (
        <div className="main bg-slate-200 flex justify-center items-center">
            <div className="flex justify-between items-center w-4/5 h-screen">
                <div className="bg-blue-100 flex-1 h-[80%] pb-4 pt-4">
                    <Sessions sessionId={sessionId} setSession={setSessionId}/>
                </div>
                <div className="bg-green-100 flex-[2] h-[80%]">
                    {sessionId && <SessionEvents sessionId={sessionId}/>}
                </div>
            </div>
        </div>
    )
}