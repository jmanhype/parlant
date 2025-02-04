import {useState} from 'react';
import {ClassNameValue, twMerge} from 'tailwind-merge';
import MessageFragment from '../message-fragment/message-fragment';

export interface Fragment {
	id: string;
	value: string;
}

const MessageFragments = ({fragmentIds, className}: {fragmentIds: string[]; className?: ClassNameValue}) => {
	const [isOpen, setIsOpen] = useState(false);

	const onToggle = (e) => {
		setIsOpen(e.target.open);
	};

	return (
		<details onToggle={onToggle} open className={twMerge(isOpen && 'bg-[#F5F6F8]', className)}>
			<summary className={twMerge('h-[34px] flex items-center justify-between ms-[24px] me-[30px] cursor-pointer text-[16px] bg-[#FBFBFB] hover:bg-white text-[#656565] hover:text-[#151515]', isOpen && '!bg-[#F5F6F8] !text-[#656565]')}>
				<span>Fragments</span>
				<img src='icons/arrow-down.svg' alt='' style={{rotate: isOpen ? '0deg' : '180deg'}} />
			</summary>
			<div className='p-[14px] pt-[10px]'>
				<div className='rounded-[14px] bg-white p-[10px]'>
					<div className='overflow-auto fixed-scroll max-h-[308px]'>
						{fragmentIds.map((fragmentId) => (
							<MessageFragment key={fragmentId} fragmentId={fragmentId} />
						))}
					</div>
				</div>
			</div>
		</details>
	);
};

export default MessageFragments;
