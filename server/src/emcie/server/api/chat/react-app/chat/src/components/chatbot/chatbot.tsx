import { ReactElement } from "react";
import Sessions from "../sessions/sessions";

export default function Chatbot(): ReactElement {
    return (
        <div className="main bg-slate-200 flex justify-center items-center">
            <div className="flex justify-between items-center w-4/5 h-[1200px]">
                <div className="bg-blue-100 flex-1 h-[80%]">
                    <Sessions />
                </div>
                <div className="bg-green-100 flex-[2] h-[80%]">agents</div>
            </div>
        </div>
    )
}