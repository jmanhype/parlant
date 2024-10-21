import { ReactElement } from "react";
import { Check, CheckCheck, CircleAlert, Clock } from "lucide-react";
import Markdown from "react-markdown";
import { Event } from "../chat/chat";

interface Props {
    event: Event
}

const statusIcon = {
    pending: <Clock height={15} />,
    error: <CircleAlert height={15} />,
    accepted: <Check height={15} />,
    acknowledged: <CheckCheck height={15} />,
    processing: <CheckCheck className="text-green-300" height={15} />,
    typing: <CheckCheck className="text-green-300" height={15} />,
    ready: <CheckCheck className="text-green-300" height={15} />,
};


const formatDateTime = (targetDate: Date | string): string => {
    const date = new Date(targetDate);
    const now = new Date();

    if (now.toDateString() === date.toDateString()) return date.toLocaleTimeString('en-US', {timeStyle: 'short', hour12: false});
    return `${date.toLocaleDateString()} ${date.toLocaleTimeString('en-US', {timeStyle: 'short', hour12: false})}`;
}

export default function Message({event}: Props): ReactElement {
    const isClient = event.source === 'client';
    const serverStatus = event.serverStatus;

    return (
        <div className={(isClient ? 'bg-blue-700 text-white self-start' : 'bg-white self-end') + ' border border-solid border-black rounded-lg p-2 m-4 mb-1 w-fit max-w-[90%] flex gap-1 items-center relative'}>
            <div className="relative">
                <Markdown>{event?.data?.message}</Markdown>
                <div className="text-end text-[unset] opacity-70 text-xs">
                    {formatDateTime(event.creation_utc)}
                </div>
            </div>
            {isClient && serverStatus && <div className="w-6 self-end">{statusIcon[serverStatus]}</div>}
        </div>
    )
}