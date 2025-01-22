import {useEffect, useState} from 'react';
import {DropdownMenu, DropdownMenuContent, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger} from '../ui/dropdown-menu';
import {Button} from '../ui/button';
import {Checkbox} from '../ui/checkbox';
import {Input} from '../ui/input';

type Type = 'General' | 'GuidelineProposer' | 'MessageEventGenerator';
type Level = 'WARNING' | 'INFO' | 'DEBUG';

const ALL_TYPES: Type[] = ['General', 'GuidelineProposer', 'MessageEventGenerator'];
const ALL_LEVELS: Level[] = ['WARNING', 'INFO', 'DEBUG'];

const typeLabels: Record<Type, string> = {
	General: 'General',
	GuidelineProposer: 'Guideline Proposer',
	MessageEventGenerator: 'Message Event Composer',
};

const LogFilters = ({applyFn, def, filterId}: {applyFn: (types: string[], level: string) => void; filterId?: number; def?: {level?: Level; types?: Type[]} | null}) => {
	const [dropdownOpen, setDropdownOpen] = useState(false);
	const [sources, setSources] = useState(structuredClone(def?.types || []));
	const [level, setLevel] = useState<Level>(def?.level || ALL_LEVELS[ALL_LEVELS.length - 1]);

	useEffect(() => {
		if (filterId) {
			const types = structuredClone(def?.types || ALL_TYPES);
			const level = def?.level || ALL_LEVELS[ALL_LEVELS.length - 1];
			setSources(types);
			setLevel(level);
			applyFn(types, level);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [filterId]);

	const changeSource = (type: Type, value: boolean) => {
		setSources((val) => {
			if (value) val.push(type);
			else val = val.filter((item) => item !== type);
			const vals = [...new Set(val)];
			return vals;
		});
	};

	return (
		<div className='flex justify-between py-[10px] pe-[10px] ps-[24px]'>
			<div className='filters-button flex items-center gap-[8px] flex-wrap'>
				{!!def?.types?.length &&
					def.types.map((type) => (
						<div key={type} className='bg-[#EBECF0] flex items-center gap-[8px] py-[5px] px-[14px] rounded-[5px]'>
							<p className='text-nowrap'>{typeLabels[type]}</p>
							<img
								src='icons/close.svg'
								alt='close'
								className='pe-[14px]'
								role='button'
								onClick={() => {
									changeSource(type, false);
									applyFn(sources, level);
								}}
							/>
						</div>
					))}
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
							{ALL_TYPES.map((type) => (
								<div key={type} className='flex items-center py-[4px] ps-[6px] space-x-2 hover:bg-[#F5F6F8] focus-within:!bg-[#EBECF0]'>
									<Checkbox id={type} defaultChecked={def?.types?.includes(type)} onCheckedChange={(isChecked) => changeSource(type, !!isChecked)} />
									<label className='text-[12px] font-normal' htmlFor={type}>
										{typeLabels[type]}
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
								onClick={() => {
									applyFn(sources, level);
									setDropdownOpen(false);
								}}
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

export default LogFilters;
