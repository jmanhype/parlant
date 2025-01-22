import {EventInterface, Log} from '@/utils/interfaces';
import {Bug, Info, Plus, TriangleAlert} from 'lucide-react';
import {ReactNode, useEffect, useState} from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import styles from '../message/message.module.scss';
import {getMessageLogs, getMessageLogsWithFilters} from '@/utils/logs';
import {Checkbox} from '../ui/checkbox';
import {Button} from '../ui/button';
import {twJoin, twMerge} from 'tailwind-merge';
import {RadioGroup, RadioGroupItem} from '../ui/radio-group';
import clsx from 'clsx';
import HeaderWrapper from '../header-wrapper/header-wrapper';
import {useSession} from '../chatbot/chatbot';
import {
	DropdownMenu,
	DropdownMenuCheckboxItem,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuPortal,
	DropdownMenuSeparator,
	DropdownMenuShortcut,
	DropdownMenuSub,
	DropdownMenuSubContent,
	DropdownMenuSubTrigger,
	DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import {Input} from '../ui/input';

const IconMap = {INFO: <Info />, DEBUG: <Bug />, WARNING: <TriangleAlert />};

const LogFilters = ({applyFn}: {applyFn: (types: any, level: string) => void}) => {
	const [dropdownOpen, setDropdownOpen] = useState(false);
	const [sources, setSources] = useState(['general', 'GuidelineProposer', 'MessageEventGenerator']);
	const [level, setLevel] = useState('DEBUG');
	const types = ['general', 'GuidelineProposer', 'MessageEventGenerator'];
	const levels = ['WARNING', 'INFO', 'DEBUG'];
	const changeSource = (type: string, value: boolean) => {
		setSources((val) => {
			if (value) val.push(type);
			else val = val.filter((item) => item !== type);
			console.log('newval', val);
			return [...val];
		});
	};
	return (
		<div className='flex justify-between py-[10px] pe-[10px]'>
			<div className='filters-button '>
				<DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
					<DropdownMenuTrigger asChild>
						<Button variant='outline' className='flex items-center gap-[6px] h-[30px]'>
							<img src='icons/filter.svg' alt='' />
							<p className='text-[15px] font-semibold'>Filters</p>
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent className='w-56 font-ubuntu-sans font-normal'>
						<DropdownMenuLabel className='flex items-center justify-between'>
							<p className='text-[15px] text-[#A9A9A9] font-normal'>Filter...</p>
							<img src='icons/close.svg' alt='close' role='button' onClick={() => setDropdownOpen(false)} />
						</DropdownMenuLabel>
						<DropdownMenuSeparator />
						<div className='flex flex-col gap-[4px] mt-[9px] pb-[11px] ps-[15px] pe-[21px]'>
							{types.map((type) => (
								<div key={type} className='flex items-center py-[4px] ps-[6px] space-x-2 hover:bg-[#F5F6F8] focus-within:!bg-[#EBECF0]'>
									<Checkbox id={type} defaultChecked={true} onCheckedChange={(isChecked) => changeSource(type, !!isChecked)} />
									<label className='text-[12px] font-normal' htmlFor={type}>
										{type}
									</label>
								</div>
							))}
						</div>
						<DropdownMenuSeparator />
						<div className={'inputs flex flex-col gap-[6px] px-[21px] pb-[14px] pt-[11px]'}>
							<div className='border rounded-[3px] h-[22px] flex items-center bg-[#FBFBFB] hover:bg-[#F5F6F8] focus-within:!bg-white'>
								<p className='ps-[10px] text-[12px] text-[#151515]'>And:</p>
								<Input className='h-[20px] !ring-0 !ring-offset-0 border-none text-[12px] bg-[#FBFBFB] hover:bg-[#F5F6F8] focus:!bg-white' />
							</div>
							<div className='border rounded-[3px] h-[22px] flex items-center bg-[#FBFBFB] hover:bg-[#F5F6F8] focus-within:!bg-white'>
								<p className='ps-[10px] text-[12px] text-[#151515]'>Or:</p>
								<Input className='h-[20px] !ring-0 !ring-offset-0 border-none text-[12px] bg-[#FBFBFB] hover:bg-[#F5F6F8] focus:!bg-white' />
							</div>
						</div>
						<DropdownMenuSeparator />
						<div className='buttons flex items-center'>
							<Button variant='ghost' className='flex-1 text-[12px] font-normal text-[#656565] h-[35px] w-[95px]'>
								Clear all
							</Button>
							<Button
								variant='outline'
								onClick={() => applyFn(sources, level)}
								className='flex-1 text-[12px] font-normal !text-white !bg-[#1E00FF] h-[35px] w-[95px]'>
								Apply
							</Button>
						</div>
					</DropdownMenuContent>
				</DropdownMenu>
			</div>
			<div className='flex gap-[20px]'>
				{/* <div>
					{types.map((type) => (
						<div key={type} className='flex items-center space-x-2'>
							<Checkbox id={type} defaultChecked={true} onCheckedChange={(isChecked) => changeSource(type, !!isChecked)} />
							<label htmlFor={type}>{type}</label>
						</div>
					))}
				</div> */}
				<div>
					<RadioGroup defaultValue={level} onValueChange={(val) => setLevel(val)}>
						{levels.map((l) => (
							<div key={l} className='flex items-center space-x-2'>
								<RadioGroupItem value={l} id={l} />
								<label htmlFor={l}>{l}</label>
							</div>
							// <div key={l} className='flex items-center space-x-2'>
							// 	<Checkbox id={l} checked={level === l} onCheckedChange={(isChecked) => setLevel(isChecked ? l : null)} />
							// 	<label htmlFor={l}>{l}</label>
							// </div>
						))}
						{/* <div className='flex items-center space-x-2'>
							<RadioGroupItem value='default' id='r1' />
							<label htmlFor='r1'>Default</label>
						</div>
						<div className='flex items-center space-x-2'>
							<RadioGroupItem value='comfortable' id='r2' />
							<Label htmlFor='r2'>Comfortable</Label>
						</div>
						<div className='flex items-center space-x-2'>
							<RadioGroupItem value='compact' id='r3' />
							<Label htmlFor='r3'>Compact</Label>
						</div> */}
					</RadioGroup>
				</div>
			</div>
			<Button className='self-end mb-[5px]' onClick={() => applyFn(sources, level)}>
				Apply
			</Button>
		</div>
	);
};

const MessageLogs = ({
	event,
	closeLogs,
	regenerateMessageFn,
}: {
	event?: EventInterface | null;
	closeLogs?: VoidFunction;
	regenerateMessageFn?: (sessionId: string) => void;
}): ReactNode => {
	const {sessionId} = useSession();
	const [filters, setFilters] = useState({});
	const [filterTabs, setFilterTabs] = useState(['filter_1']);
	const [currFilterTabs, setCurrFilterTabs] = useState('filter_1');
	const [logs, setLogs] = useState<Log[]>([]);
	const [filteredLogs, setFilteredLogs] = useState<Log[]>([]);

	useEffect(() => {
		if (logs) {
			if (!Object.keys(filters).length) setFilteredLogs(logs);
			else setFilteredLogs(getMessageLogsWithFilters(event?.correlation_id as string, filters));
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [logs, filters]);

	useEffect(() => {
		if (!event && logs.length) {
			setLogs([]);
			setFilteredLogs([]);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [event]);

	useEffect(() => {
		if (!event?.correlation_id) return;
		setLogs(getMessageLogs(event.correlation_id));
	}, [event?.correlation_id]);

	const deleteFilterTab = (tab: string) => {
		setFilterTabs((tabs) => tabs.filter((t) => t !== tab));
		if (currFilterTabs === tab) setCurrFilterTabs(filterTabs[0]);
	};

	const addFilter = () => {
		setFilterTabs((tabs) => [...tabs, `filter_${tabs.length + 1}`]);
	};

	return (
		<div className={twJoin('w-full h-full overflow-auto flex flex-col justify-start pt-0 pe-0 bg-white')}>
			<HeaderWrapper>
				{event && (
					<div className='flex items-center justify-between w-full pe-[30px]'>
						<div
							className='flex items-center gap-[7px] hover:bg-[#F5F6F8] p-[10px]'
							role='button'
							onClick={() => regenerateMessageFn?.(sessionId as string)}>
							<img src='icons/regenerate-arrow.svg' alt='regenerate' className='block group-hover:hidden h-[15px] w-[15px] min-w-[20px]' />
							<p className='font-medium text-[15px]'>Regenerate Message</p>
						</div>
						<div className='group'>
							<img
								src='icons/close-logs.svg'
								alt='close'
								role='button'
								className='group-hover:hidden'
								height={30}
								width={30}
								onClick={() => closeLogs?.()}
							/>
							<img
								src='icons/close-logs-hover.svg'
								alt='close'
								role='button'
								className='hidden group-hover:block'
								height={30}
								width={30}
								onClick={() => closeLogs?.()}
							/>
						</div>
					</div>
				)}
			</HeaderWrapper>
			{event && !!logs.length && (
				<div className='flex items-center filter-tabs border-b'>
					{filterTabs.map((tab) => (
						<div key={tab} className='flex gap-[10px] items-center p-[10px] border-e w-fit'>
							<p>{tab}</p>
							{filterTabs.length > 0 && (
								<img
									src='icons/close.svg'
									alt='close'
									className='h-[20px]'
									role='button'
									height={10}
									width={10}
									onClick={() => deleteFilterTab(tab)}
								/>
							)}
						</div>
					))}
					<div className='flex gap-[10px] items-center p-[10px] border-e w-fit'>
						<Plus role='button' onClick={addFilter} />
					</div>
				</div>
			)}
			{event && !!logs.length && <LogFilters applyFn={(types, level) => setFilters({types, level})} />}
			{!event && (
				<div className='flex flex-col m-auto justify-center items-center max-w-[378px] w-full h-full'>
					<img className='size-[224px] rounded-full' src='emcie-placeholder.svg' alt='' />
					<h2 className='text-[20px] font-medium font-inter text-[#656565] mt-[30px]'>No message has been selected</h2>
					<p className='text-[15px] font-normal font-inter text-[#656565] text-center mt-[10px]'>
						Please select one of the messages so we can give you more information
					</p>
				</div>
			)}
			{event && !logs.length && <div className='h-full flex justify-center items-center'>Logs not found</div>}
			{event && logs.length && !filteredLogs.length && <div className='h-full flex justify-center items-center'>No data</div>}
			{event && !!filteredLogs.length && (
				<div>
					{filteredLogs.map((log, i) => (
						<div key={i} className={twJoin('flex items-center gap-[5px] p-[5px] border-t')}>
							<div className='self-start'>{IconMap[log.level]}</div>
							<Markdown remarkPlugins={[remarkGfm]} className={clsx(styles.markdown, 'max-w-[-webkit-fill-available] pe-[10px]')}>
								{log?.message}
							</Markdown>
							{/* <div>{log.message}</div> */}
						</div>
					))}
				</div>
			)}
		</div>
	);
};

export default MessageLogs;
