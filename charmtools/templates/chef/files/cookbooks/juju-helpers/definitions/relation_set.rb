define :relation_set do
  args_string = params[:variables].map { |key, value| "#{key}=\"#{value}\"" }.join(' ')

  command = "relation-set #{args_string}"
  command += " -r #{params[:relation_id]}" if params[:relation_id]

  execute command do
    action :run
  end
end