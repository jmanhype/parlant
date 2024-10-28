import { ReactElement, useEffect, useRef } from 'react';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import useFetch from '@/hooks/useFetch';
import { AgentInterface } from '@/utils/interfaces';
import { useSession } from '../chatbot/chatbot';
import styles from './agent-select.module.scss';
import { NEW_SESSION_ID } from '../sessions/sessions';

export default function AgentsSelect({value}: {value?: string | undefined}): ReactElement {
    const {data} = useFetch<{agents: AgentInterface[]}>('agents');
    const {sessionId, setAgentId, agentId} = useSession();

    const selectTriggerRef = useRef<HTMLButtonElement>(null);

    useEffect(() =>  {
        if (sessionId === NEW_SESSION_ID && !agentId) selectTriggerRef?.current?.click();
    }, [sessionId, agentId]);

    const valueChanged = (val: string) => {
        setAgentId(val);
    };

    return (
        <Select value={value} onValueChange={valueChanged}>
            {sessionId && 
            <SelectTrigger aria-label='Agent' ref={selectTriggerRef} disabled={sessionId !== NEW_SESSION_ID} className={'box-shadow-none w-full h-full border-none rounded-none text-[16px] text-[#151515] font-medium' + ` ${styles.selectTrigger}`}>
                <div className='flex flex-col'>
                    <SelectValue placeholder="Select an agent" />
                    {!value && <div>Select an agent</div>}
                </div>
            </SelectTrigger>}
            <SelectContent>
                <SelectGroup>
                    {data?.agents && data.agents.map(agent =>
                        <SelectItem className='text-[16px] text-[#151515] font-medium h-[69px] font-ubuntu-sans' key={agent.id} value={agent.id}>
                            {agent.name}
                            {<p className='font-light text-[14px] text-[#A9A9A9] font-inter'>(id={agent.id})</p>}
                        </SelectItem>)
                    }
                </SelectGroup>
            </SelectContent>
        </Select>
    );
}