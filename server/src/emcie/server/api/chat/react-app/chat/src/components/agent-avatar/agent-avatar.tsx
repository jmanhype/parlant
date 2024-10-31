import { AgentInterface } from '@/utils/interfaces';
import { ReactNode } from 'react';
import Tooltip from '../ui/custom/tooltip';

interface Props {
    agent: AgentInterface;
}

const colors = ['#B4E64A', '#FFB800', '#B965CC', '#87DAC6', '#FF68C3'];

const getAvatarColor = (agentId: string) => {
    const hash = [...agentId].reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return colors[hash % colors.length];
};

const AgentAvatar = ({agent}: Props): ReactNode => {
    const background = getAvatarColor(agent.id);
    const firstLetter = agent.name[0].toUpperCase();
    return (
        <Tooltip value={agent.name} side='right' style={{transform: 'translateY(17px)', fontSize: '13px !important', fontWeight: 400, fontFamily: 'inter'}}>
            <div style={{background}} className={background + ' me-[10px] size-[38px] rounded-full flex items-center justify-center text-white text-[20px] font-semibold'}>
                {firstLetter}
            </div>
        </Tooltip>
    );
};

export default AgentAvatar;