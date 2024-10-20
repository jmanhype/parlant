import { ReactElement } from "react";
import { Check, CheckCheck } from "lucide-react";
import Markdown from "react-markdown";
import { Event } from "../chat/chat";

interface Props {
    event: Event
}

const formatDateTime = (targetDate: Date | string): string => {
    if (typeof targetDate === 'string') targetDate = new Date(targetDate);
    const now = new Date();

    if (now.toDateString() === targetDate.toDateString()) return targetDate.toLocaleTimeString('en-US', {timeStyle: 'short', hour12: false});
    return `${targetDate.toLocaleDateString()} ${targetDate.toLocaleTimeString('en-US', {timeStyle: 'short', hour12: false})}`;
}

export default function Message({event}: Props): ReactElement {
    return (
        <div className={(event.source === 'client' ? 'bg-blue-600 text-white self-start' : 'bg-white self-end') + ' border border-solid border-black rounded-lg p-2 m-4 mb-1 w-fit max-w-[90%] flex gap-1 items-center relative'}>
            <div className="relative">
                <Markdown>{event?.data?.message}</Markdown>
                <div className="text-end text-[unset] opacity-70 text-xs">
                    {formatDateTime(event.creation_utc)}
                </div>
            </div>
            {event.source === 'client' && event.serverStatus &&
            <div className="w-6 self-end">
                {event.serverStatus === 'accepted' && <Check className="self-end" height={15}/>}
                {event.serverStatus === 'acknowledged' && <CheckCheck className="self-end" height={15}/>}
                {{processing: true, typing: true, ready: true}[event.serverStatus] && <CheckCheck className="self-end text-green-300" height={15}/>}
            </div>
            }
        </div>
    )
}