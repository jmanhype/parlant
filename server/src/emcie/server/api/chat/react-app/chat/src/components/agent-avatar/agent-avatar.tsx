import { AgentInterface } from '@/utils/interfaces';
import { ReactNode } from 'react';

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
    return <div style={{background}} className={background + ' me-[10px] size-[38px] rounded-full flex items-center justify-center text-white text-[20px] font-semibold'}>{firstLetter}</div>;
};

export default AgentAvatar;