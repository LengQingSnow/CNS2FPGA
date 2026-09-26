set parts [get_parts -quiet *xcku115*]
puts "KU115_PARTS_BEGIN"
foreach part $parts { puts $part }
puts "KU115_PARTS_END"
exit
