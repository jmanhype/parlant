import {useState} from 'react';
import {ClassNameValue, twMerge} from 'tailwind-merge';
import Tooltip from '../ui/custom/tooltip';
import {copy} from '@/lib/utils';

interface Fragment {
	id: string;
	value: string;
}

const TooltipComponent = ({fragmentId}: {fragmentId: string}) => {
	return (
		<div className='group flex gap-[4px] text-[#CDCDCD] hover:text-[#151515]' role='button' onClick={() => copy(fragmentId)}>
			<div>Fragment ID: {fragmentId}</div>
			<img src='icons/copy.svg' alt='' className='invisible group-hover:visible' />
		</div>
	);
};

const MessageFragments = ({fragmentIds, className}: {fragmentIds: string[]; className?: ClassNameValue}) => {
	const [isOpen, setIsOpen] = useState(false);
	const [fragments, setFragments] = useState<Fragment[]>([
		{id: '123', value: 'Buga'},
		{id: '2222', value: 'Hello there!'},
		{
			id: 'fdsfdsfds',
			value:
				'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Ut aliquet et magna nec imperdiet. Morbi sodales sit amet orci nec iaculisLorem ipsum dolor sit amet, consectetur adipiscing elit. Ut aliquet consectetur adipiscing elit. Ut aliquet et magna nec imperdiet. ',
		},
		{
			id: 'fdsffffdsfds',
			value:
				'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Ut aliquet et magna nec imperdiet. Morbi sodales sit amet orci nec iaculisLorem ipsum dolor sit amet, consectetur adipiscing elit. Ut aliquet consectetur adipiscing elit. Ut aliquet et magna nec imperdiet. ',
		},
		{
			id: 'ddd',
			value:
				'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Ut aliquet et magna nec imperdiet. Morbi sodales sit amet orci nec iaculisLorem ipsum dolor sit amet, consectetur adipiscing elit. Ut aliquet consectetur adipiscing elit. Ut aliquet et magna nec imperdiet. ',
		},
		{
			id: 'dffdd',
			value:
				'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Ut aliquet et magna nec imperdiet. Morbi sodales sit amet orci nec iaculisLorem ipsum dolor sit amet, consectetur adipiscing elit. Ut aliquet consectetur adipiscing elit. Ut aliquet et magna nec imperdiet. ',
		},
	]);

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
						{fragments.map((fragment) => (
							<Tooltip key={fragment.id} value={<TooltipComponent fragmentId={fragment.id} />} side='top' align='start' className='rounded-[6px] rounded-bl-[0px] ml-[23px] -mb-[10px] font-medium font-ubuntu-sans'>
								<div className='group rounded-[8px] hover:bg-[#F5F6F8] hover:border-[#EDEDED] border border-transparent flex gap-[17px] text-[#656565] py-[8px] ps-[15px] pe-[38px]'>
									<img src='icons/puzzle.svg' alt='' className='group-hover:hidden w-[16px] min-w-[16px] self-start' />
									<img src='icons/puzzle-hover.svg' alt='' className='hidden group-hover:block w-[16px] min-w-[16px] self-start' />
									<div>{fragment.value}</div>
								</div>
							</Tooltip>
						))}
					</div>
				</div>
			</div>
		</details>
	);
};

export default MessageFragments;
