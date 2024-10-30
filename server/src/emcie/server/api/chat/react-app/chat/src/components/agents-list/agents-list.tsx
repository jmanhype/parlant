import useFetch from '@/hooks/useFetch';
import { AgentInterface } from '@/utils/interfaces';
import { ReactNode, useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { useSession } from '../chatbot/chatbot';
import styles from './agents-list.module.scss';
import AgentAvatar from '../agent-avatar/agent-avatar';
import { NEW_SESSION_ID } from '../chat-header/chat-header';
import { spaceClick } from '@/utils/methods';

const AgentsList = (): ReactNode => {
    const [dialogOpen, setDialogOpen] = useState(false);
    const {setAgentId, setSessionId, setAgents, sessionId} = useSession();
    const {data} = useFetch<{agents: AgentInterface[]}>('agents');

    useEffect(() => {
       if (data?.agents) setAgents(data.agents);
    }, [data?.agents, setAgents]);

    useEffect(() => {
        if (sessionId === NEW_SESSION_ID) setDialogOpen(true);
    }, [sessionId]);

    const selectAgent = (agentId: string): void => {
        setAgentId(agentId);
        setDialogOpen(false);
    };

    const closeCliked = () => {
        setDialogOpen(false);
        setSessionId(null);
    };

    return (
        <Dialog open={dialogOpen}>
            <DialogContent  className={'min-w-[604px] h-[536px] font-ubuntu-sans ' + styles.select}>
                <div className='bg-white rounded-[12px] flex flex-col h-[535px] '>
                    <DialogHeader>
                        <DialogTitle>
                            <div className='h-[68px] w-full flex justify-between items-center ps-[30px] pe-[20px]'>
                                <DialogDescription className='text-[18px] font-semibold'>Select an Agent</DialogDescription>
                                <img tabIndex={0} onKeyDown={spaceClick} onClick={closeCliked} className='cursor-pointer' src="icons/close.svg" alt="close" height={28} width={28}/>
                            </div>
                        </DialogTitle>
                    </DialogHeader>
                    <div className='flex flex-col overflow-auto'>
                        {data?.agents?.map(agent => (
                            <div tabIndex={0} onKeyDown={spaceClick} role='button' onClick={() => selectAgent(agent.id)} key={agent.id} className='cursor-pointer hover:bg-[#FBFBFB] min-h-[78px] h-[78px] w-full border-b-[0.6px] border-b-solid border-b-[#EBECF0] flex items-center ps-[30px] pe-[20px]'>
                                <AgentAvatar agent={agent}/>
                                <div>
                                    <div className='text-[16px] font-medium'>{agent.name}</div>
                                    <div className='text-[14px] font-light text-[#A9A9A9]'>(id={agent.id})</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default AgentsList;