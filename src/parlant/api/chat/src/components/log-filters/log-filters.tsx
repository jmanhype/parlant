import {memo, useEffect, useRef, useState} from 'react';
import {Button} from '../ui/button';
import {Checkbox} from '../ui/checkbox';
import {Input} from '../ui/input';
import {useDialog} from '@/hooks/useDialog';
import {Dialog, DialogClose, DialogContent, DialogDescription, DialogPortal, DialogTitle, DialogTrigger} from '../ui/dialog';
import {twMerge} from 'tailwind-merge';
import {ListFilter, X} from 'lucide-react';
import {getDistanceToRight} from '@/utils/methods';

type Type = 'General' | 'GuidelineProposer' | 'MessageEventGenerator' | 'ToolCaller';
type Level = 'WARNING' | 'INFO' | 'DEBUG';

const ALL_TYPES: Type[] = ['General', 'GuidelineProposer', 'ToolCaller', 'MessageEventGenerator'];
const ALL_LEVELS: Level[] = ['WARNING', 'INFO', 'DEBUG'];

const typeLabels: Record<Type, string> = {
	General: 'General',
	GuidelineProposer: 'Guideline Proposer',
	MessageEventGenerator: 'Message Event Composer',
	ToolCaller: 'Tool Caller',
};

const LogFilters = ({applyFn, def, filterId}: {applyFn: (types: string[], level: string, content: string[]) => void; filterId?: number; def?: {level?: Level; types?: Type[]; content: string[]} | null}) => {
	const [sources, setSources] = useState(structuredClone(def?.types || []));
	const [contentConditions, setContentConditions] = useState(structuredClone(def?.content || []));
	const [level, setLevel] = useState<Level>(def?.level || ALL_LEVELS[ALL_LEVELS.length - 1]);

	useEffect(() => {
		if (filterId) {
			const types = structuredClone(def?.types || ALL_TYPES);
			const level = def?.level || ALL_LEVELS[ALL_LEVELS.length - 1];
			const content = def?.content || [];
			setSources(types);
			setLevel(level);
			setContentConditions(content);
			applyFn(types, level, content);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [filterId]);

	useEffect(() => {
		setSources(def?.types || []);
		setLevel(def?.level || ALL_LEVELS[ALL_LEVELS.length - 1]);
		setContentConditions(def?.content || []);
	}, [def]);

	const changeSource = (type: Type, value: boolean, cb?: (sources: Type[], level: Level, contentConditions: string[]) => void) => {
		setSources((val) => {
			if (value) val.push(type);
			else val = val.filter((item) => item !== type);
			const vals = [...new Set(val)];
			cb?.(vals, level, contentConditions);
			return vals;
		});
	};

	const TypeChip = ({type}: {type: Type}) => {
		return (
			<div key={type} className='group cursor-pointer bg-[#EBECF0] h-[30px] flex items-center gap-[8px] pt-[6px] pb-[5px] ps-[14px] rounded-[5px] pe-[8px] hover:bg-[#DDDEE2]'>
				<p className='text-nowrap font-normal text-[14px]'>{typeLabels[type]}</p>
				<X role='button' className='invisible size-[18px] group-hover:visible hover:bg-[#656565] hover:text-white rounded-[3px]' onClick={() => changeSource(type, false, applyFn)} />
			</div>
		);
	};

	const CondChip = memo(({text, index}: {text: string; index: number}) => {
		return (
			<div key={text} className='group cursor-pointer bg-white border-[#656565] hover:border-[#CDCDCD] border-[1px] h-[30px] rounded-[5px] flex justify-center items-center'>
				<div className='flex items-center justify-center rounded-[3px] h-[calc(100%-4px)] w-[calc(100%-4px)] py-[5px] ps-[14px] pe-[6px] gap-[8px] bg-white group-hover:bg-[#F5F6F8] border border-[#CDCDCD] group-hover:border-[#656565]'>
					<p className='text-nowrap font-normal text-[14px]'>{text}</p>
					<X
						role='button'
						className='invisible min-w-[18px] size-[18px] group-hover:visible hover:bg-[#656565] hover:text-white rounded-[3px]'
						onClick={(e) => {
							e.stopPropagation();
							const content = contentConditions?.filter((_, i) => i !== index);
							setContentConditions(content);
							applyFn(sources, level, content);
						}}
					/>
					{/* <img
						src='icons/close-white.svg'
						alt='close'
						className='pe-[12px]'
						role='button'
						// onClick={() => {
						// 	changeSource(type, false);
						// 	applyFn(sources, level);
						// }}
					/> */}
				</div>
			</div>
		);
	});

	const FilterDialogContent = ({contentChanged, defaultValue}: {contentChanged: (text: string) => void; defaultValue?: string}) => {
		const [inputVal, setInputVal] = useState(defaultValue || '');

		const onApplyClick = () => {
			const trimmed = inputVal.trim();
			if (trimmed) contentChanged(inputVal);
		};

		return (
			<div className='px-[40px] py-[42px] flex flex-col gap-[22px]'>
				<h2 className='text-[20px] font-normal'>Filter By Content</h2>
				<div className='border rounded-[5px] h-[38px] flex items-center bg-[#FBFBFB] hover:bg-[#F5F6F8] focus-within:!bg-white'>
					<Input value={inputVal} onChange={(e) => setInputVal(e.target.value)} name='filter' className='h-[36px] !ring-0 !ring-offset-0 border-none text-[12px] bg-[#FBFBFB] hover:bg-[#F5F6F8] focus:!bg-white' />
				</div>
				<div className='buttons flex items-center gap-[24px] justify-end text-[16px] font-normal font-ubuntu-sans'>
					<DialogClose className='h-[38px] w-[84px] !bg-white text-[#656565] hover:text-[#151515]'>Cancel</DialogClose>
					<DialogClose onClick={onApplyClick} className='bg-blue-main text-white h-[38px] w-[79px] hover:bg-[#1000EB]'>
						Apply
					</DialogClose>
				</div>
			</div>
		);
	};

	const FilterDialog = ({contentChanged, content}: {contentChanged: (text: string) => void; content: string[]}) => {
		return (
			<Dialog>
				<DialogTrigger>
					<div className='group border rounded-[3px] h-[24px] flex items-center bg-[#FBFBFB] hover:bg-[#F5F6F8]'>
						<p className='ps-[10px] text-[12px] capitalize'>Content:</p>
						<Input readOnly className='h-[22px] !ring-0 !ring-offset-0 border-none text-[12px] bg-[#FBFBFB] hover:bg-[#F5F6F8]' value={content?.join(';') || ''} />
					</div>
				</DialogTrigger>
				<DialogPortal aria-hidden={false}>
					<DialogContent className='p-0' aria-hidden={false}>
						<DialogTitle className='hidden'>Filter By Content</DialogTitle>
						<DialogDescription className='hidden'>Filter By Content</DialogDescription>
						<FilterDialogContent contentChanged={contentChanged} />
					</DialogContent>
				</DialogPortal>
			</Dialog>
		);
	};

	const DropDownFilter = () => {
		const [dropdownOpen, setDropdownOpen] = useState(false);
		const [sources, setSources] = useState<Type[]>(def?.types || []);
		const [content, setContent] = useState<string[]>(def?.content || []);
		const wrapperRef = useRef<HTMLDivElement>(null);
		const [usePopupToLeft, setUsePopupToLeft] = useState(false);

		const changeSource = (type: Type, value: boolean) => {
			setSources((val) => {
				if (value) val.push(type);
				else val = val.filter((item) => item !== type);
				const vals = [...new Set(val)];
				return vals;
			});
		};

		useEffect(() => {
			if (wrapperRef?.current) {
				if (getDistanceToRight(wrapperRef.current) < 218) setUsePopupToLeft(true);
				else setUsePopupToLeft(false);
			}
		}, [wrapperRef?.current?.scrollWidth, dropdownOpen]);

		return (
			<div className='wrapper relative' ref={wrapperRef}>
				<div>
					{!def?.types?.length ? (
						<div onClick={() => setDropdownOpen(true)} role='button' className='flex hover:bg-[#E1E2E6] rounded-[5px] border items-center gap-[6px] h-[30px] px-[14px]'>
							<ListFilter className='[stroke-width:2px] size-[16px]' />
							<p className='text-[14px] font-medium'>Filters</p>
						</div>
					) : (
						<Button onClick={() => setDropdownOpen(true)} variant='outline' className='flex bg-white hover:bg-[#E1E2E6] items-center gap-[6px] w-[32px] h-[30px] p-0'>
							<img src='icons/filter.svg' alt='' />
						</Button>
					)}
				</div>
				<div className={twMerge('hidden border rounded-[5px] absolute top-0 left-0 w-[218px] bg-white', dropdownOpen && 'block', usePopupToLeft ? 'right-0 left-[unset]' : '')}>
					<div className='flex justify-between items-center'>
						<div className='flex items-center gap-[6px] h-[30px] px-[14px]'>
							<ListFilter className='[stroke-width:2px] size-[16px]' />
							<p className='text-[14px] font-medium'>Filters</p>
						</div>
						<div role='button' onClick={() => setDropdownOpen(false)} className='hover:bg-[#EBECF0] flex h-[24px] w-[24px] items-center me-[2px] justify-center'>
							<img src='icons/close.svg' alt='close' />
						</div>
					</div>
					<hr className='bg-[#EBECF0]' />
					<div className='flex flex-col gap-[4px] mt-[9px] pb-[11px] ps-[15px] pe-[21px]'>
						{ALL_TYPES.map((type) => (
							<div key={type} className={twMerge('flex items-center py-[4px] ps-[6px] space-x-2 hover:bg-[#F5F6F8]', sources.includes(type) && 'bg-[#EBECF0]')}>
								<Checkbox id={type} defaultChecked={def?.types?.includes(type)} className='border-black !bg-white' onCheckedChange={(isChecked) => changeSource(type, !!isChecked)} />
								<label className='text-[12px] font-normal w-full cursor-pointer' htmlFor={type}>
									{typeLabels[type]}
								</label>
							</div>
						))}
					</div>
					<hr className='bg-[#EBECF0]' />
					<div className={'inputs flex flex-col gap-[6px] px-[21px] pb-[14px] pt-[11px]'}>
						<FilterDialog contentChanged={(inputVal) => setContent((val) => [...val, inputVal])} content={content} />
					</div>
					<hr className='bg-[#EBECF0]' />
					<div className='buttons flex items-center'>
						<Button onClick={() => applyFn([], 'DEBUG', [])} variant='ghost' className='flex-1 text-[12px] font-normal text-[#656565] h-[35px] w-[95px]'>
							Clear all
						</Button>
						<Button
							variant='ghost'
							onClick={() => {
								applyFn(sources, level, content);
								setDropdownOpen(false);
							}}
							className='flex-1 text-[12px] font-normal !text-white bg-blue-main h-[35px] w-[95px] hover:bg-[#1000EB]'>
							Apply
						</Button>
					</div>
				</div>
			</div>
		);
	};

	return (
		<div className='flex justify-between py-[10px] pe-[10px] ps-[24px] bg-white min-h-fit h-[70px]'>
			<div className='filters-button flex items-center gap-[8px] flex-wrap'>
				{!!def?.types?.length && def.types.map((type) => <TypeChip key={type} type={type} />)}
				{def?.content?.map((c: string, index: number) => (
					<Dialog key={c}>
						<DialogTrigger>
							<CondChip key={c} text={c} index={index} />
						</DialogTrigger>
						<DialogPortal>
							<DialogContent className='p-0'>
								<DialogTitle hidden>Filter By Content</DialogTitle>
								<DialogDescription hidden>Filter By Content</DialogDescription>
								<FilterDialogContent
									defaultValue={c}
									contentChanged={(text) => {
										const updatedContent = contentConditions.map((item, i) => (i === index ? text : item));
										applyFn(sources, level, updatedContent);
									}}
								/>
							</DialogContent>
						</DialogPortal>
					</Dialog>
					// <CondChip key={c} text={c} index={index} />
				))}
				<DropDownFilter />
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
				{/* <div>
					<RadioGroup defaultValue={level} onValueChange={(val) => setLevel(val)}>
						{ALL_LEVELS.map((l) => (
							<div key={l} className='flex items-center space-x-2'>
								<RadioGroupItem value={l} id={l} />
								<label htmlFor={l}>{l}</label>
							</div>
						))}
					</RadioGroup>
				</div> */}
			</div>
			{/* <Button className='self-end mb-[5px]' onClick={() => applyFn(sources, level)}>
				Apply
			</Button> */}
		</div>
	);
};

export default memo(LogFilters);
